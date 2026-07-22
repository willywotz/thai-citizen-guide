# SRS — 03: API

← [ดัชนี](README.md)

---

เอกสารนี้สรุปทุก endpoint ของ OneChat backend เอกสารรายเวอร์ชัน (v1–v5) อยู่ที่ [`../api/`](../api/) แยกไฟล์ต่อเวอร์ชัน แต่ละไฟล์ใช้โครงสร้างหัวข้อเดียวกันทุกไฟล์ ต่างกันแค่เนื้อหา — เพื่อให้เทียบกันได้ง่ายและหาข้อมูลที่ต้องการได้เร็ว

Base URL: ขึ้นกับ deployment เช่น `http://<host>:8000`
Schema ที่เป็น source of truth (machine-readable): [openapi.yaml](../api/openapi.yaml) — ครอบคลุม `/v1`–`/v3/chat`; v4/v5 (SSE) และ `/v1/llm-settings` ยังไม่มีใน spec นี้ อ้างอิงเอกสาร `.md` รายเวอร์ชันแทน

## ดัชนีเอกสาร API รายเวอร์ชัน

| ไฟล์ | เนื้อหา |
|---|---|
| [../api/v1.md](../api/v1.md) | `/v1/chat` — คำตอบรวมที่ LLM synthesis เป็น Markdown เดียว |
| [../api/v2.md](../api/v2.md) | `/v2/chat` — คำตอบดิบแยกรายหน่วยงาน ไม่มี LLM synthesis |
| [../api/v3.md](../api/v3.md) | `/v3/chat` — คำตอบแยก section ต่อหัวข้อ + debug struct (JSON ก้อนเดียว) |
| [../api/v4.md](../api/v4.md) | `/v4/chat` — ข้อมูลชุดเดียวกับ v3 แต่ stream แบบ SSE |
| [../api/v5.md](../api/v5.md) | `/v5/chat` — เหมือน v4 + บทสรุปภาพรวมพร้อม inline citation ไว้บนสุด + thread name |

แต่ละไฟล์เรียงหัวข้อแบบเดียวกัน: **1. สรุป → 2. Endpoint → 3. Request Body → 4. Response → 5. พฤติกรรมพิเศษ → 6. Errors → 7. Multi-turn → 8. ตัวอย่าง → 9. เทียบกับเวอร์ชันอื่น** (v4/v5 มีหัวข้อ Response แตกย่อยเพิ่มสำหรับ SSE event)

---

## ตารางเปรียบเทียบ

| | [v1](../api/v1.md) | [v2](../api/v2.md) | [v3](../api/v3.md) | [v4](../api/v4.md) | [v5](../api/v5.md) |
|---|---|---|---|---|---|
| Response type | JSON | JSON | JSON | SSE stream | SSE stream |
| คำตอบรวม (`answer`) | ✓ LLM synthesis | ✗ ไม่มี | ✓ raw concat | ✓ raw concat | ✓ บทสรุป + raw concat |
| คำตอบดิบรายหน่วยงาน | ✗ | ✓ `agencies[]` | ✓ `sections[]` | ✓ `sections[]` | ✓ `sections[]` (เหมือน v4 ทุกตัวอักษร) |
| Debug struct | ✗ | ✗ | ✓ | ✓ | ✓ |
| Smart fallback (ตอบไม่ได้) | ✗ ข้อความตายตัว | ✗ ไม่มี field รวม | ✓ | ✓ | ✓ (เหมือน v3/v4 ทุกประการ) |
| Partial-section fallback* | ✗ | ✗ | ✓ | ✓ | ✓ |
| บทสรุปภาพรวมพร้อม citation `[n]` | ✗ | ✗ | ✗ | ✗ | ✓ (เฉพาะ `summary`, ไม่ปนใน `sections[]`) |
| Thread name | ✗ | ✗ | ✗ | ✗ | ✓ |
| Progress ระหว่างรอ | ✗ | ✗ | ✗ | ✓ | ✓ |
| `meta.synthesized` | `true`/`false` | `false` เสมอ | `false` เสมอ | — (ใน `answer`) | — (ใน `answer`) |
| เวลาโดยทั่วไป (`search`) | ~30–90s | ~30–90s | ~30–90s | ~30–90s (เห็น progress) | ~30–90s (เพิ่ม LLM call เดียวสำหรับสรุป) |

\* Partial-section fallback = เมื่อคำถามแตกเป็นหลาย sub-question แล้วบางอันไม่มี agency ไหนตอบผ่าน แต่อันอื่นผ่าน — sub-question ที่ตกไปยังได้ section ของตัวเอง (เนื้อหาเป็นคำตอบจริงของ agency ที่ถูกถาม) แทนที่จะหายไปเงียบๆ

### เลือกใช้เวอร์ชันไหน

| ต้องการ | ใช้ |
|---|---|
| คำตอบสำเร็จรูปพร้อมแสดงผลทันที ไม่สนใจรายละเอียดหน่วยงาน | [v1](../api/v1.md) |
| ควบคุมการแสดงผลเองทั้งหมดจากคำตอบดิบ ไม่ให้ LLM แตะเนื้อหาเลย | [v2](../api/v2.md) |
| Structured sections + debug แต่ไม่ต้องการ progress ระหว่างรอ | [v3](../api/v3.md) |
| ต้องการแสดง progress แบบ real-time ("กำลังถามกรม X...") | [v4](../api/v4.md) |
| ต้องการบทสรุปภาพรวมบนสุดพร้อม citation + thread name สำหรับ sidebar สนทนา | [v5](../api/v5.md) |

---

## Request Body (ใช้ร่วมกันทุกเวอร์ชัน v1–v5)

```json
{
  "query": "การทำบัตรประชาชนใหม่ต้องไปที่ไหน",
  "mcp_endpoint_url": "http://185.84.161.145/mcp",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Field | Type | จำเป็น | คำอธิบาย |
|---|---|---|---|
| `query` | string | ✅ | คำถามจากผู้ใช้; whitespace ซ้ำถูก normalize; ว่างล้วน → `400` |
| `mcp_endpoint_url` | string (URL) | ✅ | MCP catalog endpoint สำหรับ discover หน่วยงานแบบ runtime ต่อคำขอ; ถูก SSRF guard (บล็อก IP วงใน) |
| `session_id` | string | ❌ | สำหรับ multi-turn; ไม่ส่ง → server สร้าง UUID ใหม่ (ไม่มี history) |

ส่ง field เกิน → `400` (`extra = "forbid"`)

---

## Multi-turn (session_id)

รองรับทุกเวอร์ชัน (v1–v5) ผ่าน `session_id`:

1. Frontend สร้าง UUID ตอนเริ่ม session
2. ส่ง `session_id` เดิมทุก request ในบทสนทนานั้น
3. Server echo กลับใน `meta.session_id` (v1–v3) หรือ event `done` (v4–v5)
4. ไม่ส่ง `session_id` → server สร้างใหม่ทุกครั้ง ไม่มี history

ต้องตั้ง `REDIS_URL` — ถ้าไม่มี ระบบ stateless ทุก request (มี Redis แล้วเก็บประวัติสูงสุด 5 turns, TTL ~30 นาที คำตอบ assistant ถูก truncate ที่ 800 ตัวอักษรก่อนเก็บ)

`session_id` เดียวกันนี้ยังถูกส่งต่อไปยังหน่วยงานปลายทางที่ declare field `session_id` / `conversation_id` / `thread_id` ใน MCP catalog ด้วย — agency ที่รองรับ session memory จะ map turn ของผู้ใช้ต่อเนื่องได้ตั้งแต่ turn 2

v5 เท่านั้นที่ `session_id` มีผลต่อ**เนื้อหา**คำตอบโดยตรง ผ่าน `thread_name` ที่ถูกตรึงไว้ตั้งแต่คำถามแรกของ session — ดู [v5 § 4.5](../api/v5.md#45-done--เพิ่ม-field-thread_name)

---

## Errors (ใช้ร่วมกันทุกเวอร์ชัน)

### 400 — Request ผิด

```json
{ "error": "Missing query parameter" }
```

เกิดเมื่อ: ไม่มี `query` / เป็น whitespace ล้วน, `mcp_endpoint_url` ไม่ถูกต้องหรือชี้ IP วงใน (SSRF block), หรือส่ง field เกิน

### 500 — Internal error

```json
{ "error": "Internal server error" }
```

ข้อผิดพลาดภายในที่ดักไม่ได้ — internal error ไม่ถูก expose ออกมา ปลอดภัยสำหรับ retry

---

## Endpoint เสริม (Debug/Ops — ไม่ผูกกับเวอร์ชันไหน)

### `GET /health`

```json
{ "status": "ok" }
```

### `GET /v1/mcp/agencies`

ดึงรายชื่อ + config ของหน่วยงานทั้งหมดจาก MCP server ที่ระบุ (เครื่องมือ debug)

| Query param | จำเป็น | คำอธิบาย |
|---|---|---|
| `mcp_endpoint_url` | ✅ | URL ของ MCP server |

คืนเป็น array โดยตรง (ไม่มี wrapper):

```json
[
  {
    "id": "019d5cf7-9dc4-70e0-b4a5-3f549d0cf7b9",
    "name": "กรมการปกครอง",
    "description": "ข้อมูลทะเบียนราษฎร์ บัตรประชาชน",
    "endpoint_url": "https://api.example.org/dopa/chat",
    "data_scope": ["บัตรประชาชน", "ทะเบียนบ้าน"],
    "request_query_field": "query",
    "request_static_payload": {}
  }
]
```

### `GET /v1/mcp/health`

discover หน่วยงานแล้วยิงคำถามทดสอบจริงไปแต่ละแห่ง (เครื่องมือ debug)

| Query param | จำเป็น | ค่าเริ่มต้น | คำอธิบาย |
|---|---|---|---|
| `mcp_endpoint_url` | ✅ | — | URL ของ MCP server |
| `test_query` | ❌ | `"test"` | คำถามทดสอบ |

คืนเป็น array โดยตรง — แต่ละรายการมี `status` (`online`/`offline`), `answer_preview` (200 ตัวอักษรแรก, `null` ถ้า offline), `error` (`null` ถ้า online)

---

## เอกสารที่เกี่ยวข้อง

| เอกสาร | เนื้อหา |
|---|---|
| [01-overview.md](01-overview.md) | OneChat คืออะไร, ขอบเขต, ข้อจำกัดหลัก |
| [02-architecture.md](02-architecture.md) | โครงสร้างชั้น, LangGraph flow, node แต่ละตัว |
| [04-agents.md](04-agents.md) | งาน LLM แต่ละชนิด (classify / verify / synthesize / executive summary / no-answer) |
| [../api/openapi.yaml](../api/openapi.yaml) | OpenAPI spec (machine-readable) |
| [06-bugs.md](06-bugs.md) | ปัญหาที่รู้อยู่ + แนวทางแก้ |
