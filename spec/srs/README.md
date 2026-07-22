# SRS — OneChat Backend

**เวอร์ชัน API ปัจจุบัน:** v1–v5 | **สถานะ:** Draft

## ดัชนีเอกสาร

| ไฟล์ | เนื้อหา |
|---|---|
| [01-overview.md](01-overview.md) | OneChat คืออะไร, ขอบเขต, ข้อจำกัดหลัก, tech stack ย่อ |
| [02-architecture.md](02-architecture.md) | โครงสร้างชั้น, LangGraph flow, node แต่ละตัว, การตัดสินใจเชิงออกแบบ |
| [03-api.md](03-api.md) | ภาพรวม + ตารางเปรียบเทียบ API ทั้ง 5 เวอร์ชัน (รายละเอียดเต็มแต่ละเวอร์ชันอยู่ที่ [`../api/`](../api/)) |
| [04-agents.md](04-agents.md) | งาน LLM 6 ชนิด (analyze / verify / synthesize / trim / connect / synthesize_no_answer) + agency adapter |
| [05-roadmap.md](05-roadmap.md) | สิ่งที่เสร็จแล้ว vs ยังไม่เสร็จ |
| [06-bugs.md](06-bugs.md) | ปัญหาที่รู้อยู่ + แนวทางแก้ |
| [07-mcp-spec.md](07-mcp-spec.md) | สัญญา/มาตรฐานการเชื่อมต่อ MCP server เข้ากับ OneChat |

## เอกสารอื่น

| Path | เนื้อหา |
|---|---|
| [../api/](../api/) | คู่มือ API รายเวอร์ชัน (v1.md–v5.md) — โครงสร้างหัวข้อเดียวกันทุกไฟล์ |
| [../api/openapi.yaml](../api/openapi.yaml) | OpenAPI spec (machine-readable; ครอบคลุม `/v1`–`/v3/chat`; v4/v5/llm-settings ยังไม่มี) |
| [../diagrams/workflow.drawio](../diagrams/workflow.drawio) | Workflow diagram (เปิดด้วย draw.io) |

## สรุปสถานะ ณ ปัจจุบัน

### Done (ทำงานได้จริง)
- FastAPI endpoints `/v1/chat`–`/v3/chat` (JSON), `/v4/chat`–`/v5/chat` (SSE streaming)
- LangGraph pipeline: validate → resolve agencies → analyze query (classify + decompose) → invoke agencies (parallel) → verify relevance → [v5 only] summarize → format ต่อเวอร์ชัน
- Smart no-answer fallback (v3/v4/v5): agency เดียวตอบไม่ตรง → ใช้คำตอบจริงของ agency นั้น; หลาย agency ไม่มีใครตอบตรงเลย → LLM สังเคราะห์รวม
- Partial-section fallback (v3/v4/v5): sub-question ที่ไม่มี agency ไหนผ่าน ยังได้ section ของตัวเอง แม้ sub-question อื่นในคำขอเดียวกันจะผ่าน
- Section ordering ตามลำดับ sub-question ที่ user ถาม เสมอ (ไม่ใช่ตามลำดับ agency ตอบเสร็จ)
- v5: executive summary พร้อม `[n]` citation + `references[]` ไว้บนสุดของ `answer` (1 LLM call ต่อ request, ไม่ใช่ต่อ agency), `sections[]` เหมือน v4 ทุกตัวอักษร (ไม่มีการตัด/แก้เนื้อหาอีกต่อไป), `thread_name` ต่อ session
- Multi-turn session history ผ่าน Redis (`REDIS_URL`) — ไม่มีก็ stateless
- Reliability stack ต่อ agency: timeout → retry (exponential-jitter) → circuit breaker
- MCP catalog discovery แบบ runtime ต่อคำขอ (SSE → JSON-RPC → plain HTTP fallback), timeout บังคับใช้จริงแล้ว
- Structured request-summary log ต่อ request (`onechat.summary` logger) รวม `partial_fallback_count`/`labels`
- **LLM provider system**: runtime-configurable main/fallback (vLLM หรือ OpenRouter) ผ่าน `MultiplexedLLMClient`, config + cost/usage log ใน Postgres, ตั้งค่าผ่านหน้า LLM Setting (`/v1/llm-settings`) ไม่ใช่ env var
- **Fail-loud/fail-closed degrade policy**: `analyze_query`/`generate_markdown` LLM fail → raise; `verify_relevance` LLM fail → fallback `0.0` (fail-closed แทนที่จะผ่านเงียบ ๆ)
- **Chitchat/out_of_scope response standardization**: ลงท้าย "ครับ" เสมอ, ไม่มี emoji, ประโยคมาตรฐานเดียวกันเสมอ; `out_of_scope` ครอบคลุม prompt injection/jailbreak ด้วย
- **SSE crash recovery** (v4/v5): unhandled node exception → ปิดทุก step ค้างเป็น `error` + fallback answer แทน connection ค้าง
- **Debug console redesign**: persistent sidebar + session thread list, Overview cost/usage dashboard, LLM Setting page

### Known Issues (ดูรายละเอียดที่ [06-bugs.md](06-bugs.md))
- v4/v5 event ชนิด `ErrorEvent` ประกาศไว้ใน schema แต่ไม่เคย emit จริง (ผลกระทบเดิมแก้แล้ว — stream ยังปิดด้วย `done` เสมอ)
- SSRF guard บล็อก IP วงในแต่ไม่บังคับ HTTPS

### Not Started
- OpenAPI spec ที่ครอบคลุม v4/v5/llm-settings แบบ machine-readable (ตอนนี้มีแค่คำอธิบายในเอกสาร `.md`)
