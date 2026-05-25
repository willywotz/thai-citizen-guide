# Semantic Duplicate Question Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect semantically similar questions within a 3-day window and return cached answers, skipping downstream API calls.

**Architecture:** pgvector for semantic similarity search with pg_trgm fallback when embedding API is unavailable. New embedding service + similarity service in `backend/app/services/`. Integration at the start of all three chat endpoints. Background embedding generation after saving messages.

**Tech Stack:** PostgreSQL 16 + pgvector extension, pg_trgm (built-in contrib), OpenAI embedding API (text-embedding-3-small, 384 dims), Tortoise ORM + Aerich migrations, httpx for async HTTP, pytest + pytest-asyncio for tests.

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/config.py` | Add embedding API settings |
| Modify | `backend/app/models/conversation.py` | Add embedding column to Message |
| Create | `backend/migrations/models/15_20260525_embed_col.py` | Migration: add embedding column + pgvector/pg_trgm extensions + indexes |
| Create | `backend/app/services/__init__.py` | (already exists, empty) |
| Create | `backend/app/services/embedding.py` | Generate embeddings via external API |
| Create | `backend/app/services/similarity.py` | Find similar questions via vector/trigram search |
| Modify | `backend/app/routers/chat.py` | Integrate similarity check into all 3 endpoints |
| Create | `tests/__init__.py` | Test package init |
| Create | `tests/conftest.py` | Tortoise ORM test setup |
| Create | `tests/test_embedding.py` | Embedding service tests |
| Create | `tests/test_similarity.py` | Similarity search tests |
| Modify | `backend/pyproject.toml` | Add pgvector dependency |

---

### Task 1: Add pgvector dependency and config settings

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add `pgvector` to dependencies in `pyproject.toml`**

Add `pgvector>=0.3.0` to the dependencies list (after `tortoise-orm[asyncpg]>=0.21.0`):

```toml
    "tortoise-orm[asyncpg]>=0.21.0",
    "pgvector>=0.3.0",
```

- [ ] **Step 2: Add embedding config settings to `backend/app/config.py`**

Add these fields to the `Settings` class:

```python
    # Embedding service
    EMBEDDING_API_URL: str = "https://api.openai.com/v1/embeddings"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 384
    EMBEDDING_TIMEOUT: int = 5
    SIMILARITY_THRESHOLD: float = 0.95
    SIMILARITY_WINDOW_DAYS: int = 3
```

- [ ] **Step 3: Install the new dependency**

Run: `cd backend && pip install pgvector>=0.3.0`

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/app/config.py
git commit -m "feat: add pgvector dependency and embedding config settings"
```

---

### Task 2: Add embedding column to Message model and create migration

**Files:**
- Modify: `backend/app/models/conversation.py`
- Create: `backend/migrations/models/15_20260525_embed_col.py`

- [ ] **Step 1: Add embedding column to Message model**

In `backend/app/models/conversation.py`, add the import at the top:

```python
from pgvector.utils import SparseVec
```

Then add the embedding field to the `Message` class, after the `errors` field and before `created_at`:

```python
    embedding = fields.CharField(max_length=50000, null=True)  # JSON-encoded vector, nullable until populated
```

We use `CharField` with JSON encoding instead of a native vector field because Tortoise ORM doesn't have a built-in pgvector field. The similarity service will handle encoding/decoding.

- [ ] **Step 2: Create the Aerich migration**

Run: `cd backend && aerich migrate --name "add_embedding_and_extensions"`

This generates a migration file. Edit the generated migration to include:

```python
async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        ALTER TABLE "messages" ADD COLUMN "embedding" TEXT;
        CREATE INDEX IF NOT EXISTS idx_messages_content_trgm ON "messages" USING gin (content gin_trgm_ops);
        CREATE INDEX IF NOT EXISTS idx_messages_role_created ON "messages" (role, created_at) WHERE role = 'user';
    """

async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS idx_messages_role_created;
        DROP INDEX IF EXISTS idx_messages_content_trgm;
        ALTER TABLE "messages" DROP COLUMN "embedding";
    """
```

Note: We use `TEXT` for the embedding column instead of `vector(384)` because Tortoise ORM doesn't natively support pgvector column types. The similarity service will cast the column to vector at query time using SQL.

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/conversation.py backend/migrations/models/
git commit -m "feat: add embedding column to Message model with pgvector and pg_trgm extensions"
```

---

### Task 3: Create embedding service

**Files:**
- Create: `backend/app/services/embedding.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_embedding.py`

- [ ] **Step 1: Create test infrastructure**

Create `tests/__init__.py` (empty file).

Create `tests/conftest.py`:

```python
import pytest
from tortoise import Tortoise
from backend.app.config import TORTOISE_ORM


@pytest.fixture(autouse=True)
async def init_db():
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()
```

- [ ] **Step 2: Write the failing test for embedding generation**

Create `tests/test_embedding.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from backend.app.services.embedding import generate_embedding


@pytest.mark.asyncio
async def test_generate_embedding_returns_vector():
    mock_response = {
        "data": [{"embedding": [0.1] * 384}],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 5, "total_tokens": 5},
    }
    with patch("backend.app.services.embedding.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_client.post.return_value = mock_resp

        result = await generate_embedding("วิธีต่อทะเบียนบ้าน")
        assert result is not None
        assert len(result) == 384
        assert result[0] == 0.1


@pytest.mark.asyncio
async def test_generate_embedding_returns_none_on_failure():
    with patch("backend.app.services.embedding.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_resp = AsyncMock()
        mock_resp.status_code = 500
        mock_client.post.return_value = mock_resp

        result = await generate_embedding("test query")
        assert result is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_embedding.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.services.embedding'`

- [ ] **Step 4: Implement the embedding service**

Create `backend/app/services/embedding.py`:

```python
import json
import logging
from backend.app.config import settings

import httpx

logger = logging.getLogger(__name__)


async def generate_embedding(text: str) -> list[float] | None:
    """Generate embedding vector for text via external API. Returns None on failure."""
    if not settings.EMBEDDING_API_KEY:
        logger.warning("EMBEDDING_API_KEY not configured, skipping embedding generation")
        return None

    url = settings.EMBEDDING_API_URL
    headers = {
        "Authorization": f"Bearer {settings.EMBEDDING_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.EMBEDDING_MODEL,
        "input": text,
        "dimensions": settings.EMBEDDING_DIMENSIONS,
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=settings.EMBEDDING_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["data"][0]["embedding"]
                logger.warning(f"Embedding API returned status {resp.status_code}: {resp.text[:200]}")
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning(f"Embedding API attempt {attempt + 1} failed: {e}")

    logger.error("Embedding API failed after 3 attempts")
    return None


def encode_embedding(vector: list[float]) -> str:
    """Encode embedding vector to JSON string for storage."""
    return json.dumps(vector)


def decode_embedding(stored: str) -> list[float]:
    """Decode embedding vector from JSON string stored in DB."""
    return json.loads(stored)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_embedding.py -v`
Expected: Both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/embedding.py tests/__init__.py tests/conftest.py tests/test_embedding.py
git commit -m "feat: add embedding service with external API and retry logic"
```

---

### Task 4: Create similarity search service

**Files:**
- Create: `backend/app/services/similarity.py`
- Create: `tests/test_similarity.py`

- [ ] **Step 1: Write the failing test for similarity search**

Create `tests/test_similarity.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.services.similarity import find_similar_question


@pytest.mark.asyncio
async def test_find_similar_question_with_embedding_hit():
    """When vector similarity >= threshold, return the cached answer."""
    from backend.app.models.conversation import Message, Conversation

    # Mock the database query chain
    with patch.object(Message, "filter") as mock_filter:
        mock_qs = AsyncMock()

        # First call: find similar user message
        similar_user_msg = MagicMock()
        similar_user_msg.id = "user-msg-id"
        similar_user_msg.content = "วิธีต่อทะเบียนบ้าน"
        similar_user_msg.conversation_id = "conv-id"

        # Second call: find assistant answer
        assistant_msg = MagicMock()
        assistant_msg.content = "คำตอบเก่า"
        assistant_msg.id = "asst-msg-id"

        mock_qs.order_by.return_value = mock_qs
        mock_qs.limit.return_value = mock_qs
        mock_qs.first.return_value = similar_user_msg
        mock_filter.return_value = mock_qs

        with patch.object(Message, "get") as mock_get:
            mock_get.return_value = assistant_msg

            result = await find_similar_question(
                query="จะลงทะเบียนบ้านทำยังไง",
                embedding=[0.1] * 384,
            )
            assert result is not None
            user_msg, asst_msg = result
            assert user_msg.content == "วิธีต่อทะเบียนบ้าน"
            assert asst_msg.content == "คำตอบเก่า"


@pytest.mark.asyncio
async def test_find_similar_question_no_hit():
    """When no similar question found, return None."""
    from backend.app.models.conversation import Message

    with patch.object(Message, "filter") as mock_filter:
        mock_qs = AsyncMock()
        mock_qs.order_by.return_value = mock_qs
        mock_qs.limit.return_value = mock_qs
        mock_qs.first.return_value = None
        mock_filter.return_value = mock_qs

        result = await find_similar_question(
            query="คำถามใหม่มากๆ",
            embedding=[0.1] * 384,
        )
        assert result is None


@pytest.mark.asyncio
async def test_find_similar_question_trigram_fallback():
    """When embedding is None, fall back to trigram search."""
    from backend.app.models.conversation import Message

    with patch.object(Message, "filter") as mock_filter:
        mock_qs = AsyncMock()
        similar_user_msg = MagicMock()
        similar_user_msg.id = "user-msg-id"
        similar_user_msg.content = "วิธีต่อทะเบียนบ้าน"
        similar_user_msg.conversation_id = "conv-id"

        mock_qs.order_by.return_value = mock_qs
        mock_qs.limit.return_value = mock_qs
        mock_qs.first.return_value = similar_user_msg
        mock_filter.return_value = mock_qs

        with patch.object(Message, "get") as mock_get:
            assistant_msg = MagicMock()
            assistant_msg.content = "คำตอบเก่า"
            mock_get.return_value = assistant_msg

            result = await find_similar_question(
                query="วิธีต่อทะเบียนบ้าน",
                embedding=None,
            )
            assert result is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_similarity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.services.similarity'`

- [ ] **Step 3: Implement the similarity search service**

Create `backend/app/services/similarity.py`:

```python
import json
import logging
from datetime import timedelta

from tortoise.expressions import Q
from django.utils import timezone

from backend.app.config import settings
from backend.app.models.conversation import Message, Conversation
from backend.app.services.embedding import decode_embedding

logger = logging.getLogger(__name__)


async def find_similar_question(
    query: str,
    embedding: list[float] | None = None,
    threshold: float = 0.95,
    window_days: int = 3,
) -> tuple[Message, Message] | None:
    """Find a similar question from the last `window_days` days.

    Uses pgvector cosine similarity if embedding is provided,
    falls back to pg_trgm text similarity if embedding is None.

    Returns (user_message, assistant_message) if a match is found above threshold,
    None otherwise.
    """
    cutoff = timezone.now() - timedelta(days=window_days)

    if embedding is not None:
        match = await _vector_search(query, embedding, threshold, cutoff)
    else:
        match = await _trigram_search(query, threshold, cutoff)

    if match is None:
        return None

    # Find the assistant answer for the matched question
    try:
        assistant_msg = await Message.get(
            parent_id=match.id,
            role="assistant",
        )
    except Exception:
        logger.info(f"No assistant answer found for message {match.id}")
        return None

    # Only return answers from successful conversations
    try:
        conv = await Conversation.get(id=match.conversation_id)
        if conv.status != "success":
            logger.info(f"Skipping cached answer from non-success conversation {conv.id}")
            return None
    except Exception:
        logger.warning(f"Conversation {match.conversation_id} not found")
        return None

    return (match, assistant_msg)


async def _vector_search(
    query: str,
    embedding: list[float],
    threshold: float,
    cutoff,
) -> Message | None:
    """Search for similar questions using pgvector cosine distance."""
    from backend.app.services.embedding import encode_embedding

    threshold_distance = 1 - threshold  # cosine distance = 1 - cosine similarity
    embedding_json = encode_embedding(embedding)

    # Use raw SQL with pgvector for cosine distance search
    # Tortoise ORM doesn't natively support vector operators, so we use raw SQL
    results = await Message.raw(
        """
        SELECT id, content, conversation_id, embedding
        FROM messages
        WHERE role = 'user'
          AND created_at >= %s
          AND embedding IS NOT NULL
          AND (embedding::vector <=> %s::vector) < %s
        ORDER BY (embedding::vector <=> %s::vector)
        LIMIT 1
        """,
        [cutoff, embedding_json, threshold_distance, embedding_json],
    )

    if not results:
        return None

    row = results[0]
    # Fetch the full ORM object
    return await Message.get(id=row["id"])


async def _trigram_search(
    query: str,
    threshold: float,
    cutoff,
) -> Message | None:
    """Search for similar questions using pg_trgm text similarity."""
    results = await Message.raw(
        """
        SELECT id, content, conversation_id, similarity(content, %s) AS sim_score
        FROM messages
        WHERE role = 'user'
          AND created_at >= %s
          AND similarity(content, %s) >= %s
        ORDER BY similarity(content, %s) DESC
        LIMIT 1
        """,
        [query, cutoff, query, threshold, query],
    )

    if not results:
        return None

    row = results[0]
    return await Message.get(id=row["id"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_similarity.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/similarity.py tests/test_similarity.py
git commit -m "feat: add similarity search service with pgvector and pg_trgm fallback"
```

---

### Task 5: Integrate similarity check into chat endpoints

**Files:**
- Modify: `backend/app/routers/chat.py`

- [ ] **Step 1: Add imports to `chat.py`**

At the top of `backend/app/routers/chat.py`, add:

```python
from backend.app.services.similarity import find_similar_question
from backend.app.services.embedding import generate_embedding, encode_embedding
```

- [ ] **Step 2: Add similarity check to `chat_external` endpoint**

In the `chat_external` function (line ~465), after `query = body.query.strip()` and the empty query check, but before the `payload = {"query": ...}` line, add the similarity check:

```python
    # Check for similar question in cache
    embedding = await generate_embedding(query)
    cached = await find_similar_question(query=query, embedding=embedding)
    if cached:
        user_msg, asst_msg = cached
        logger.info(f"Cache hit for query: {query[:50]}... (similar to: {user_msg.content[:50]})")
        return {
            "success": True,
            "data": {
                "message_id": asst_msg.id,
                "answer": asst_msg.content,
                "references": asst_msg.sources if asst_msg.sources else [],
                "agentSteps": asst_msg.agent_steps if asst_msg.agent_steps else [],
                "agencies": [],
                "confidence": 0.95,
            },
            "conversation_id": str(user_msg.conversation_id),
            "responseTime": 0,
            "cached": True,
        }
```

Then, after creating the `query_msg` in `chat_external`, add a background task to generate and store the embedding:

```python
    background_tasks.add_task(_store_embedding, query_msg.id, query)
```

- [ ] **Step 3: Add similarity check to `chat_internal` endpoint**

In the `chat_internal` function (line ~376), after `query = body.query.strip()` and the empty query check, add the same similarity check block (same as above, but without `background_tasks` since this endpoint doesn't use them).

After creating the user `Message` in `chat_internal`, add:

```python
    # Schedule embedding generation
    import asyncio
    asyncio.create_task(_store_embedding(str(query_msg.id), query))
```

Note: `chat_internal` doesn't use `BackgroundTasks`, so we use `asyncio.create_task` instead.

- [ ] **Step 4: Add similarity check to `chat_stream` endpoint**

In the `chat_stream` function (line ~572), after `query = body.query.strip()` and the empty query check, add:

```python
    # Check for similar question in cache
    embedding = await generate_embedding(query)
    cached = await find_similar_question(query=query, embedding=embedding)
    if cached:
        user_msg, asst_msg = cached
        logger.info(f"Cache hit for stream query: {query[:50]}... (similar to: {user_msg.content[:50]})")
        # Return SSE stream with cached answer
        async def cached_stream():
            yield _sse_event("answer", {"answer": asst_msg.content})
            yield _sse_event("done", {"session_id": conversation_id, "total_ms": 0, "cached": True})
        return StreamingResponse(cached_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

Then in `_save_stream_conversation`, after creating `query_msg`, add:

```python
    background_tasks.add_task(_store_embedding, str(query_msg.id), query)
```

- [ ] **Step 5: Add the `_store_embedding` helper function**

Add this function near the end of `chat.py` (before `classify_message_category`):

```python
async def _store_embedding(message_id: str, query: str):
    """Generate embedding for a message and store it in the database."""
    from backend.app.services.embedding import generate_embedding, encode_embedding

    embedding = await generate_embedding(query)
    if embedding is not None:
        encoded = encode_embedding(embedding)
        await Message.filter(id=message_id).update(embedding=encoded)
```

- [ ] **Step 6: Verify the changes compile**

Run: `cd backend && python -c "from backend.app.routers.chat import router; print('OK')"`

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/chat.py
git commit -m "feat: integrate similarity check into all three chat endpoints"
```

---

### Task 6: Add `cached` field to response schemas

**Files:**
- Modify: `backend/app/schemas/chat.py`

- [ ] **Step 1: Add `cached` field to `ChatResponseData`**

In `backend/app/schemas/chat.py`, add `cached: bool = False` to the `ChatResponseData` class:

```python
class ChatResponseData(BaseModel):
    message_id: uuid.UUID
    answer: str
    references: list[dict[str, Any]]
    agentSteps: list[dict[str, Any]]
    agencies: list[dict[str, Any]]
    confidence: float
    cached: bool = False  # True when answer comes from similarity cache
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/chat.py
git commit -m "feat: add cached field to ChatResponseData schema"
```

---

### Task 7: Run database migration and verify end-to-end

**Files:** None (verification only)

- [ ] **Step 1: Run the Aerich migration**

Run: `cd backend && aerich upgrade`

This creates the pgvector and pg_trgm extensions, adds the embedding column, and creates indexes.

- [ ] **Step 2: Start the backend server and verify it starts**

Run: `cd backend && uvicorn backend.app.main:app --reload`

Verify: Server starts without errors. Check logs for any issues with pgvector or pg_trgm extensions.

- [ ] **Step 3: Test similarity check with a manual request**

Send two similar queries via curl or the frontend:
1. First query: `POST /api/v1/chat/stream` with `{"query": "วิธีต่อทะเบียนบ้าน"}`
2. Second query: `POST /api/v1/chat/stream` with `{"query": "จะลงทะเบียนบ้านทำยังไง"}`

The second query should return faster and include `"cached": true` in the response if the embedding service is working.

- [ ] **Step 4: Commit any remaining fixes**

If any fixes were needed during verification, commit them:

```bash
git add -A
git commit -m "fix: adjustments from end-to-end verification"
```

---

### Task 8: Add integration test for similarity cache flow

**Files:**
- Create: `tests/test_similarity_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_similarity_integration.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from backend.app.services.similarity import find_similar_question
from backend.app.services.embedding import generate_embedding


@pytest.mark.asyncio
async def test_full_cache_flow_no_hit():
    """New query with no similar questions in DB returns None."""
    from backend.app.models.conversation import Message

    with patch.object(Message, "filter") as mock_filter:
        mock_qs = AsyncMock()
        mock_qs.order_by.return_value = mock_qs
        mock_qs.limit.return_value = mock_qs
        mock_qs.first.return_value = None
        mock_filter.return_value = mock_qs

        result = await find_similar_question(
            query="คำถามที่ไม่มีในระบบเลย",
            embedding=[0.1] * 384,
        )
        assert result is None


@pytest.mark.asyncio
async def test_embedding_generation_and_encoding():
    """Verify embedding is generated and can be encoded/decoded."""
    from backend.app.services.embedding import encode_embedding, decode_embedding

    vector = [0.1, 0.2, 0.3, -0.4]
    encoded = encode_embedding(vector)
    decoded = decode_embedding(encoded)
    assert decoded == vector
    assert len(decoded) == 4


@pytest.mark.asyncio
async def test_trigram_fallback_called_when_embedding_none():
    """When embedding is None, trigram search is used."""
    from backend.app.models.conversation import Message

    with patch("backend.app.services.similarity._trigram_search", new_callable=AsyncMock) as mock_trigram:
        with patch("backend.app.services.similarity._vector_search", new_callable=AsyncMock) as mock_vector:
            mock_trigram.return_value = None

            await find_similar_question(query="test", embedding=None)

            mock_trigram.assert_called_once()
            mock_vector.assert_not_called()
```

- [ ] **Step 2: Run integration tests**

Run: `cd backend && pytest tests/test_similarity_integration.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_similarity_integration.py
git commit -m "test: add integration tests for similarity cache flow"
```