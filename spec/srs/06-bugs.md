# SRS — 06: ปัญหาที่รู้อยู่

← [ดัชนี](README.md)

---

> ปัญหาที่ตรวจพบจากการอ่านโค้ดปัจจุบัน · งานค้างเชิงฟีเจอร์ดู [05-roadmap.md](05-roadmap.md)
> ระดับ: **High** | **Medium** | **Low**

---

## B1 — ~~MCP discovery ไม่มี timeout~~ · **แก้แล้ว**

**ตำแหน่ง:** `app/services/mcp_catalog.py` — `HttpMCPCatalogClient`

เดิม field `timeout_ms: int = 8000` ประกาศไว้แต่ไม่เคยถูกส่งต่อให้ `Client()`/`call_tool()` ตอนนี้แก้แล้ว — `discover()` คำนวณ `timeout_sec = self.timeout_ms / 1000.0` แล้วส่งเข้าทั้ง `Client(url, timeout=timeout_sec)` และ `call_tool(..., timeout=timeout_sec)` จริง (ยืนยันด้วยการทดสอบจริง: MCP endpoint ที่ไม่ตอบ error ออกมาเป็น `"Timed out ... Waited 8.0 seconds"` แทนที่จะค้าง ~30 วินาทีแบบเดิม)

---

## B2 — SSRF guard ไม่บังคับ HTTPS · Medium

**ตำแหน่ง:** `app/models/agency.py` — `_validate_ssrf_url`

`_validate_ssrf_url` บล็อก IP แบบ private / loopback / link-local / reserved และ hostname ต้องห้าม แต่ **ไม่ได้บังคับ scheme เป็น HTTPS** — `http://` ที่ชี้ public IP ผ่าน validator ได้

**ความขัดแย้งกับเอกสาร:** `CLAUDE.md` ระบุว่า _"endpoint_url and mcp_endpoint_url both require HTTPS and are SSRF-protected"_ ซึ่งไม่ตรงกับโค้ด (ครึ่งหลังจริง ครึ่งแรกไม่จริง)

**ผลกระทบ:** การเรียกหน่วยงานและ MCP อาจวิ่งผ่าน `http://` แบบ plaintext; security posture อ่อนกว่าที่เอกสารอ้าง ในทางปฏิบัติ MCP endpoint ที่ใช้อยู่ก็เป็น `http://` (เช่น `http://185.84.161.145/mcp`) — การบังคับ HTTPS ตอนนี้จะทำให้ใช้ไม่ได้

**แนวทางแก้:** เลือกอย่างใดอย่างหนึ่ง — (ก) บังคับ HTTPS จริงใน validator แล้วย้าย MCP endpoint ไป HTTPS, หรือ (ข) แก้ `CLAUDE.md` ให้ตรงความจริงว่า HTTP ก็ยอมรับ

---

## B3 — ~~Environment variable ที่ไม่ถูกใช้~~ · **แก้แล้ว**

**ตำแหน่ง:** `.env.example` เทียบกับ `app/core/settings.py`

เดิม `.env` example เคยประกาศ `MAX_AGENCIES`, `OPENROUTER_FALLBACK_MODEL`, `DEBUG_MODE` ที่ไม่มีใน `Settings` เลย ตอนนี้ไฟล์ env example ถูกรวมเหลือไฟล์เดียว (`.env.example`) และตัวแปรทั้งสามถูกลบออกแล้ว (`OPENROUTER_*` ทั้งหมดถูกแทนที่ด้วยระบบ LLM provider ผ่าน Postgres — ดู [04-agents.md](04-agents.md))

---

## B4 — v4/v5 ไม่เคยส่ง `ErrorEvent` (แต่ผลกระทบเดิมแก้แล้ว) · Low

**ตำแหน่ง:** `app/models/stream.py` (`ErrorEvent`), `app/graph/orchestrator.py` (`run_stream`), `app/api/chat.py` (`_stream_generator`)

`stream.py` ยังนิยาม `ErrorEvent` ไว้ และ `run_stream`/`_stream_generator` ยัง**ไม่เคย emit event ชนิด `error`** จริง (คำกล่าวเดิมยังตรง) — แต่ **ผลกระทบที่เคยมีถูกแก้ไปแล้ว**: `run_stream` ตอนนี้ครอบ `try/except Exception` รอบ `astream()` ทั้งหมด เมื่อ node ไหน raise ที่ไม่ถูกจับไว้ก่อน จะ:
1. log `graph_stream_failed`
2. ปิดทุก `step` ที่ยังค้างอยู่ด้วย `{"event": "step", "data": {"status": "error", ...}}`
3. ส่ง fallback `answer` event ("ขออภัย เกิดข้อผิดพลาดระหว่างประมวลผลคำถามของคุณ กรุณาลองใหม่อีกครั้ง") แล้วปิดด้วย `done` ตามปกติ

**ผลกระทบปัจจุบัน (เบากว่าเดิมมาก):** frontend ยังแยกไม่ออกระหว่าง "คำตอบจริง" กับ "fallback หลัง crash" จาก event type เพียงอย่างเดียว (ต้องดูเนื้อหา `answer` หรือ `step.status`) แต่ **connection ไม่หลุดค้างอีกต่อไป** — stream ปิดสมบูรณ์ด้วย `done` เสมอ ไม่ว่า node จะ crash หรือไม่

**แนวทางแก้ (เหลือ, priority ต่ำลง):** ใช้ `ErrorEvent` จริงแทน fallback-as-answer เพื่อให้ frontend แยกกรณีได้ชัดกว่า — หรือลบ `ErrorEvent` ออกเพื่อไม่ให้สัญญาเกินจริง เพราะ path ปัจจุบันไม่ได้ใช้มันเลย

---

## เอกสารที่เกี่ยวข้อง

- [05-roadmap.md](05-roadmap.md) — งานค้างเชิงฟีเจอร์
- [02-architecture.md](02-architecture.md) · [04-agents.md](04-agents.md)
