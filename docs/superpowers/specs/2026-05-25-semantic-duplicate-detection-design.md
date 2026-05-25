# Semantic Duplicate Question Detection

## Problem

Users ask similar questions repeatedly (e.g., "วิธีต่อทะเบียนบ้าน" vs "จะลงทะเบียนบ้านทำยังไง"). Each call hits the external API, wasting tokens and adding latency. We want to detect semantically similar questions within a 3-day window and return cached answers instead.

## Requirements

- **Semantic similarity**: Match questions with the same meaning but different wording (Thai language)
- **Global cache**: Cached answers are shared across all users
- **All endpoints**: Apply to external, internal, and SSE streaming paths
- **Return cached answer as-is**: No regeneration when a duplicate is found
- **3-day window**: Only check questions from the last 3 days
- **95% similarity threshold**: Cosine similarity >= 0.95 to count as a duplicate
- **Fallback to text similarity**: If embedding API is unavailable, fall back to pg_trgm text similarity

## Architecture

### Query Flow (New)

```
User question arrives
  → Generate embedding via external API
  → Search Message table for similar question (last 3 days, cosine similarity >= 0.95)
  → If match found:
      → Return cached assistant answer immediately (skip API call)
  → Else if embedding API failed:
      → Fallback: pg_trgm text similarity search (>= 0.95)
      → If match found: return cached answer
  → Else (no match):
      → Call downstream API as normal
      → Background: generate and store embedding for the new question
```

### Components

#### 1. Database Changes

- Add `pgvector` extension to PostgreSQL
- Add `embedding` column to `Message` model: `VectorField(dim=384)` (nullable — populated async)
- Add IVFFlat index on embedding column for fast cosine similarity search
- Add GIN index on `content` column with `pg_trgm` operator class for fallback text search
- Add composite index on `(role, created_at)` where `role='user'` for efficient scanning

#### 2. Embedding Service (`backend/app/services/embedding.py`)

- `generate_embedding(text: str) -> list[float]`: Call external embedding API (OpenAI `text-embedding-3-small` or OneChat embedding endpoint)
- Retry logic: 2 retries with exponential backoff
- Timeout: 5 seconds
- On failure: return `None` (caller falls back to pg_trgm or skips cache)

#### 3. Similarity Search Service (`backend/app/services/similarity.py`)

- `find_similar_question(query: str, embedding: list[float] | None, threshold: float = 0.95, days: int = 3) -> tuple[Message, Message] | None`
  - If embedding provided: vector cosine similarity search via pgvector
  - If embedding is None: fallback to pg_trgm text similarity
  - Returns `(user_message, assistant_message)` pair if match found, `None` otherwise
- Only searches `role='user'` messages with `created_at >= NOW() - INTERVAL '{days} days'`
- For vector search: uses `embedding <=> query_vector` (cosine distance) with threshold `1 - similarity < 0.05`
- For text search: uses `similarity(content, query)` from pg_trgm with threshold >= 0.95
- Excludes conversations with `status != 'success'`

#### 4. Chat Router Integration

Insert similarity check at the start of all three endpoints:

- `POST /chat` (chat_external, line ~464): Before proxying to OneChat
- `POST /chat/internal` (chat_internal, line ~376): Before running LangGraph
- `POST /chat/stream` (chat_stream, line ~572): Before proxying to OneChat SSE

Logic per endpoint:
1. Receive query
2. Generate embedding (async, with timeout)
3. Call `find_similar_question(query, embedding)`
4. If match found: return cached answer in the expected response format
5. If no match: proceed with normal API call
6. After saving user message: schedule background task to generate and store embedding

#### 5. Background Embedding Generation

- After saving a user message, schedule a background task to generate its embedding
- `async def generate_and_store_embedding(message_id: UUID)`: generate embedding and update the message's `embedding` column
- If generation fails: message remains with `embedding=NULL`, excluded from vector search but available for trigram fallback

### Thresholds

| Method | Threshold | Condition |
|--------|-----------|-----------|
| pgvector cosine similarity | >= 0.95 | `1 - cosine_distance >= 0.95` |
| pg_trgm text similarity | >= 0.95 | `similarity(content, query) >= 0.95` |

### Error Handling

| Scenario | Behavior |
|----------|----------|
| Embedding API down | Fall back to pg_trgm text search |
| pg_trgm also fails (rare) | Skip cache, call API normally |
| Cached answer from failed conversation (`status != 'success'`) | Skip cache, call API normally |
| Embedding generation fails for new message | Message saved without embedding; trigram fallback still works |

### Response Format

When a cached answer is returned, the response includes a `cached: true` field so the frontend can optionally indicate this to the user. All three endpoints' response formats will be extended with this field.

For SSE stream: emit a single `cached` event with the cached answer, followed by a `done` event.

## Dependencies

- PostgreSQL `pgvector` extension (already available as `pgvector/pgvector` Docker image or can be installed in existing Postgres 16)
- PostgreSQL `pg_trgm` extension (included in PostgreSQL contrib)
- External embedding API (OpenAI or OneChat endpoint)
- Python `pgvector` package (for Tortoise ORM integration)

## Migration Plan

1. Install pgvector extension in PostgreSQL
2. Add embedding column to Message model (nullable, populated async)
3. Create indexes (IVFFlat on embedding, GIN on content with pg_trgm)
4. Backfill: optionally generate embeddings for existing user messages (can be done gradually via background task)
5. Deploy embedding service and similarity search service
6. Integrate into chat router endpoints