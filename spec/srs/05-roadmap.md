# SRS — 05: Roadmap

← [ดัชนี](README.md)

---

> สถานะ ณ ปัจจุบันของโค้ด · ปัญหาเชิงบั๊กแยกไว้ที่ [06-bugs.md](06-bugs.md)

## เสร็จแล้ว (shipped)

| ความสามารถ | หมายเหตุ |
|---|---|
| Endpoint `/v1/chat` | คำตอบ Markdown ที่ LLM เรียบเรียงรวม |
| Endpoint `/v2/chat` | คำตอบดิบแยกรายหน่วยงาน |
| Endpoint `/v3/chat` | คำตอบแยก section + debug struct |
| Endpoint `/v4/chat` | SSE streaming — event ตามขั้นตอน pipeline |
| Endpoint `/v5/chat` | เหมือน v4 + `summarize_answer` — บทสรุปภาพรวมพร้อม inline citation ไว้บนสุด (1 LLM call ต่อ request) + thread name; `sections[]` เหมือน v4 ทุกตัวอักษร |
| MCP runtime discovery | discover หน่วยงานต่อ request ผ่าน `fastmcp.Client`, timeout บังคับใช้จริงแล้ว (ดู B1 ที่แก้แล้วใน [06-bugs.md](06-bugs.md)) |
| Analyze query (CoT) | normalize + classify intent + decompose + route + label ใน LLM call เดียว; LLM fail → raise ตรง ๆ (ไม่ degrade เงียบ ๆ) |
| Intent: search / chitchat / capability / out_of_scope | ครบ 4 ประเภท — `out_of_scope` กรองคำหยาบ/ข่มขู่/ไร้สาระ/ผิดกฎหมาย/prompt injection ตอบ refusal โดยไม่เรียก agency (คำถามนอก scope ข้อมูลไม่นับ); chitchat/refusal มาตรฐานเดียวกัน (ลงท้าย "ครับ", ไม่มี emoji, ประโยคเดียวกันเสมอ) |
| Parallel agency invocation | `asyncio.as_completed` + timeout + retry + circuit breaker |
| Verify relevance | LLM ให้คะแนนคำตอบต่อหน่วยงาน; LLM fail → fallback `0.0` (fail-closed) |
| LLM synthesis (v1) | `generate_markdown` |
| Debug struct (v3/v4/v5) | routing, ผลต่อหน่วยงาน, timing ต่อขั้น |
| v4/v5 live progress | `agency_start`/`agency_responded`/`agency_verified` ส่ง live; `step` มีคู่ running/done; unhandled node exception → ปิดทุก step ค้างเป็น `error` + fallback answer แทนที่จะปล่อย connection ค้าง |
| Session history | Redis (optional) — 5 turns, TTL ~30 นาที |
| Session forwarding to agencies | propagate `session_id` ไป agency ที่ declare `session_id` / `conversation_id` / `thread_id` ใน MCP — agency-side memory ทำงานต่อเนื่อง |
| SSRF guard | บล็อก IP วงใน (private/loopback/link-local/reserved) |
| **LLM provider system** | runtime-configurable main/fallback provider (vLLM หรือ OpenRouter) ผ่านหน้า LLM Setting; เก็บ config + cost/usage log ใน Postgres (`llm_provider_config`, `llm_call_log`); API key เข้ารหัสด้วย pgcrypto |
| **Debug console redesign** | persistent sidebar + session thread list, Overview cost/usage dashboard, LLM Setting page (แทนหน้า Logs เดิม) |
| Observability | structlog JSON, `request_id`, header `X-Response-Time-MS` |
| Debug endpoint | `/v1/mcp/agencies`, `/v1/mcp/health`, `/v1/llm-settings` (+ `/models`, `/usage/summary`) |
| Deployment | Docker multi-stage + nginx + zero-downtime deploy (`scripts/deploy.sh deploy`), pre-flight checks รวม `LLM_SETTINGS_ENCRYPTION_KEY` |
| Test suite | pytest — ครอบคลุม adapters, graph, nodes, invoke, models, api, e2e, openapi, llm settings/multiplexed client (120 tests) |

## ยังไม่เสร็จ / ทำบางส่วน

| รายการ | สถานะ | รายละเอียด |
|---|---|---|
| v4/v5 event `error` (ชนิด `ErrorEvent`) | **ยังไม่ทำ** — แต่ผลกระทบเดิมแก้แล้ว | `ErrorEvent` นิยามใน `app/models/stream.py` แล้ว แต่ `run_stream` ไม่เคย emit event ชนิดนี้จริง ตอนนี้ crash ปิด stream ด้วย fallback answer + `done` แทน (connection ไม่ค้างแล้ว) ดู B4 ใน [06-bugs.md](06-bugs.md) |
| บังคับ HTTPS บน endpoint | **ยังไม่ทำ** | `_validate_ssrf_url` บล็อก IP วงในแต่ไม่บังคับ HTTPS ดู [06-bugs.md](06-bugs.md) B2 |
| OpenAPI spec v4/v5/llm-settings | **ทำบางส่วน** | `docs/api/openapi.yaml` ครอบคลุม `/v1`–`/v3/chat` เท่านั้น; v4/v5 อยู่ใน [03-api.md](03-api.md)/`docs/api/v4.md`,`v5.md` เท่านั้น, `/v1/llm-settings` ยังไม่มีใน spec เลย |

## หมายเหตุ

- ไม่มีฐานข้อมูลของ**หน่วยงาน** — เป็นการตัดสินใจเชิงออกแบบ ไม่ใช่งานค้าง (ดู [01-overview.md](01-overview.md)) ส่วน Postgres ที่มีอยู่ตอนนี้ใช้เก็บ LLM provider config + cost log เท่านั้น ไม่เกี่ยวกับหน่วยงาน
- `MultiplexedLLMClient` มี retry/fallback model แล้ว (main → fallback + circuit breaker + cost logging ต่อ config role) — ต่างจากเดิมที่ `OpenRouterClient` ไม่มีกลไกนี้เลย

## เอกสารที่เกี่ยวข้อง

- [06-bugs.md](06-bugs.md) — รายละเอียดปัญหาที่รู้อยู่
- [01-overview.md](01-overview.md) · [02-architecture.md](02-architecture.md)
