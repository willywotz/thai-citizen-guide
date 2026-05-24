# OneChat v4 Streaming API (SSE)

เอกสารสำหรับทีม Frontend — วิธีเชื่อมต่อและใช้งาน `POST /v4/chat`

---

## 1. ภาพรวม

`/v4/chat` ให้คำตอบเหมือน `/v3/chat` ทุกประการ แต่เปลี่ยนรูปแบบการรับส่ง:

| | v3 | v4 |
|---|---|---|
| รูปแบบ | ขอครั้งเดียว รอจนเสร็จ ได้ JSON ก้อนเดียว | เปิด connection ค้างไว้ ส่ง event ทีละขั้นแบบ real-time |
| Content-Type | `application/json` | `text/event-stream` (SSE) |
| ผลลัพธ์สุดท้าย | `ChatV3Response` | event ชื่อ `answer` (ข้อมูลชุดเดียวกับ `ChatV3Data`) |
| ประโยชน์ | — | แสดงความคืบหน้าให้ผู้ใช้เห็นระหว่างรอ (discover → classify → invoke → ...) |

ทำไมต้องมี v4: pipeline ใช้เวลานานได้ถึง ~60–90 วินาที (หน่วยงานปลายทางเป็น LLM agent ที่ตอบช้า) ถ้ารอแบบ v3 หน้าเว็บจะค้างเงียบ ๆ ทั้งช่วงนั้น v4 ส่งสัญญาณบอกทุกขั้นตอนเพื่อให้แสดง progress ได้

---

## 2. Endpoint

```
POST /v4/chat
Content-Type: application/json
Accept: text/event-stream
```

Response headers:

```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

---

## 3. Request body

โครงสร้างเดียวกับ v1/v2/v3:

```json
{
  "query": "อยากเปิดร้านอาหารและขายเหล้า ต้องขออนุญาตอะไรบ้าง",
  "session_id": "abc-123",
  "mcp_endpoint_url": "http://185.84.161.145/mcp"
}
```

| ฟิลด์ | ชนิด | จำเป็น | คำอธิบาย |
|---|---|---|---|
| `query` | string | ใช่ | คำถามจากผู้ใช้ ห้ามว่าง (ช่องว่างซ้ำจะถูกตัดอัตโนมัติ) |
| `session_id` | string | ไม่ | ใช้ผูกประวัติการสนทนา ถ้าไม่ส่ง server จะสร้าง UUID ใหม่ให้ (ดูได้จาก event `done`) |
| `mcp_endpoint_url` | string (URL) | ใช่ | MCP catalog endpoint สำหรับ discover หน่วยงาน ต้องเป็น public URL (ถูกบล็อก IP วงใน) |

ส่งฟิลด์เกินมาจะได้ `400` (`extra = "forbid"`)

---

## 4. รูปแบบ SSE

ทุก event ส่งมาเป็นบล็อกข้อความ ปิดท้ายด้วยบรรทัดว่าง:

```
event: <ชื่อ event>
data: <JSON หนึ่งบรรทัด>

```

ตัวอย่าง raw จริงจาก wire:

```
event: step
data: {"name": "discover", "status": "running", "ms": null}

event: agencies
data: {"agencies": [...], "count": 3}

```

ข้อควรรู้:
- `data:` เป็น JSON บรรทัดเดียวเสมอ (ไม่มี newline ภายใน) — parse ด้วย `JSON.parse()` ได้ตรง ๆ
- ข้อความภาษาไทยส่งเป็น UTF-8 ไม่ได้ escape (`ensure_ascii=false`)
- event แต่ละตัวคั่นด้วย `\n\n`

ข้อควรระวัง: ห้ามใช้ `EventSource` ของ browser — `EventSource` รองรับเฉพาะ `GET` แต่ v4 เป็น `POST` ที่มี body จึงต้องใช้ `fetch()` แล้วอ่าน `ReadableStream` ของ response body เอง โดยแยก event ที่คั่นด้วย `\n\n` และ parse บรรทัด `data:` เป็น JSON

---

## 5. ลำดับเหตุการณ์ (event flow)

### กรณี `intent = search` (คำถามทั่วไป — เส้นทางหลัก)

```
step      {name: "discover",   status: "running"}      <- เปิด connection ปุ๊บ ส่งทันที
step      {name: "discover",   status: "done"}
agencies  {agencies: [...], count: N}
step      {name: "classify",   status: "running"}
step      {name: "classify",   status: "done"}
intent    {intent: "search", ...}
routing   {sub_questions: [...]}
step      {name: "invoke",     status: "running"}
agency_start      {agency_id: "A", ...}                  <- ส่งทีเดียวทุกหน่วยงานที่จะเรียก
agency_start      {agency_id: "B", ...}
agency_responded  {agency_id: "B", status: "ok"}         <- ทยอยมาตามที่หน่วยงานตอบกลับ
agency_responded  {agency_id: "A", status: "error"}
step      {name: "invoke",     status: "done"}
step      {name: "verify",     status: "running"}
agency_verified   {agency_id: "B", status: "passed", relevance_score: 1.0}
step      {name: "verify",     status: "done"}
step      {name: "synthesize", status: "running"}
step      {name: "synthesize", status: "done"}
answer    {answer: "...", sections: [...], errors: [...], debug: {...}}
done      {session_id: "...", total_ms: 66351}
```

### กรณี `intent = chitchat` หรือ `capability` (ทักทาย / ถามความสามารถ)

ข้ามขั้น invoke/verify ทั้งหมด:

```
step      {name: "discover",   status: "running"}
step      {name: "discover",   status: "done"}
agencies  {agencies: [...], count: N}
step      {name: "classify",   status: "running"}
step      {name: "classify",   status: "done"}
intent    {intent: "chitchat", ...}
step      {name: "synthesize", status: "running"}
step      {name: "synthesize", status: "done"}
answer    {answer: "สวัสดีครับ ...", sections: [], errors: [], debug: {...}}
done      {session_id: "...", total_ms: 4200}
```

หลักการสำคัญ:
- ทุก step มาเป็นคู่ `running` แล้วตามด้วย `done` เสมอ ใช้จับว่าตอนนี้อยู่ขั้นไหน
- `done` คือ event ปิดท้ายเสมอ หลังจากนั้น server จะปิด connection
- ถ้า connection ปิดโดยไม่มี `done` ถือว่าเกิดข้อผิดพลาด (ดูข้อ 8)

---

## 6. Event reference

### `step` — สถานะของแต่ละขั้นใน pipeline

```json
{ "name": "classify", "status": "running", "ms": null }
{ "name": "classify", "status": "done",    "ms": 5580.5 }
```

| ฟิลด์ | ชนิด | คำอธิบาย |
|---|---|---|
| `name` | enum | `discover` / `classify` / `invoke` / `verify` / `synthesize` |
| `status` | enum | `running` (เริ่มขั้นนี้) / `done` (จบขั้นนี้) |
| `ms` | number \| null | เวลาที่ใช้ของขั้นนี้ (มิลลิวินาที) — มีค่าเฉพาะตอน `done`, ตอน `running` เป็น `null` |

ความหมายแต่ละขั้น:

| name | ทำอะไร | เวลาโดยทั่วไป |
|---|---|---|
| `discover` | ดึงรายชื่อหน่วยงานจาก MCP catalog | ~0.5 วินาที (ถ้า endpoint ล่ม จะรอนานถึง ~30 วินาที) |
| `classify` | LLM วิเคราะห์คำถาม จัดประเภท intent + แตกคำถามย่อย | ~5–12 วินาที |
| `invoke` | ยิงคำถามไปทุกหน่วยงานพร้อมกัน | สูงสุด ~60 วินาที (ตาม timeout ของหน่วยงานช้าสุด) |
| `verify` | LLM ให้คะแนนความเกี่ยวข้องของแต่ละคำตอบ | ~1–3 วินาที |
| `synthesize` | เรียบเรียงคำตอบสุดท้ายเป็น Markdown | แปรผัน |

---

### `agencies` — รายชื่อหน่วยงานที่ค้นพบ

```json
{
  "agencies": [
    {
      "id": "019d5cf7-9dc4-70e0-b4a5-3f549d0cf7b9",
      "name": "กรมการปกครอง",
      "description": "ระบบตรวจสอบข้อมูลทะเบียนราษฎร์ บัตรประชาชน และงานปกครอง",
      "data_scope": ["อาวุธปืน", "โรงแรม", "สถานบริการ"]
    }
  ],
  "count": 3
}
```

| ฟิลด์ | ชนิด | คำอธิบาย |
|---|---|---|
| `agencies[].id` | string | รหัสหน่วยงาน — ใช้เป็น key อ้างอิงใน event อื่น ๆ |
| `agencies[].name` | string | ชื่อหน่วยงาน |
| `agencies[].description` | string \| null | คำอธิบาย |
| `agencies[].data_scope` | string[] | ขอบเขตข้อมูลที่หน่วยงานนี้ดูแล |
| `count` | number | จำนวนหน่วยงานที่ค้นพบ (อาจเป็น `0` ถ้า MCP ล่ม) |

---

### `intent` — ผลการจัดประเภทคำถาม

```json
{
  "intent": "search",
  "normalized_query": "อยากเปิดร้านอาหารและขายเหล้า ต้องขออนุญาตอะไรบ้าง",
  "reasoning": "User wants to know permits for opening a restaurant..."
}
```

| ฟิลด์ | ชนิด | คำอธิบาย |
|---|---|---|
| `intent` | enum | `search` (ค้นหาคำตอบ) / `chitchat` (ทักทาย) / `capability` (ถามว่าระบบทำอะไรได้) |
| `normalized_query` | string \| null | คำถามที่ถูกปรับให้สมบูรณ์ (เช่นเติมบริบทจากประวัติ) |
| `reasoning` | string \| null | เหตุผลของการจัดประเภท (ภาษาอังกฤษ — ใช้ debug) |

---

### `routing` — การแตกคำถามย่อยและจับคู่หน่วยงาน

ส่งเฉพาะตอน `intent = search` เท่านั้น

```json
{
  "sub_questions": [
    {
      "section_label": "ขออนุญาตเปิดร้านอาหารและขายเหล้า",
      "broadcast": false,
      "agencies": [
        {
          "id": "019d5cf7-9dc4-70e0-b4a5-3f549d0cf7b9",
          "name": "กรมการปกครอง",
          "query": "ต้องขออนุญาตอะไรบ้างในการเปิดร้านอาหารที่ขายเหล้า"
        }
      ]
    }
  ]
}
```

| ฟิลด์ | ชนิด | คำอธิบาย |
|---|---|---|
| `sub_questions[].section_label` | string | ชื่อกลุ่ม/หัวข้อย่อย (ตรงกับ `section_label` ใน event `agency_*` และ `title` ใน `answer.sections`) |
| `sub_questions[].broadcast` | boolean | `true` = ถามทุกหน่วยงาน (LLM ไม่มั่นใจ), `false` = เจาะจงหน่วยงาน |
| `sub_questions[].agencies[]` | array | หน่วยงานที่จะถูกถามในหัวข้อนี้ พร้อมคำถามที่ปรับเฉพาะหน่วยงาน |

---

### `agency_start` — เริ่มยิงคำถามไปหน่วยงานหนึ่ง

ส่งทีเดียวพร้อมกันทุกหน่วยงานทันทีที่ขั้น `invoke` เริ่ม ใช้เพื่อสร้าง placeholder/spinner รอไว้ล่วงหน้า

```json
{
  "agency_id": "019d5cf7-9dc4-70e0-b4a5-3f549d0cf7b9",
  "agency_name": "กรมการปกครอง",
  "query": "ต้องขออนุญาตอะไรบ้างในการเปิดร้านอาหารที่ขายเหล้า",
  "section_label": "ขออนุญาตเปิดร้านอาหารและขายเหล้า"
}
```

| ฟิลด์ | ชนิด | คำอธิบาย |
|---|---|---|
| `agency_id` | string | รหัสหน่วยงาน |
| `agency_name` | string \| null | ชื่อหน่วยงาน |
| `query` | string | คำถามที่ส่งไปหน่วยงานนี้จริง |
| `section_label` | string \| null | หัวข้อย่อยที่หน่วยงานนี้สังกัด |

---

### `agency_responded` — หน่วยงานหนึ่งตอบกลับ (จากขั้น invoke)

ส่ง 1 ครั้งต่อหน่วยงาน ทันทีที่หน่วยงานนั้นตอบกลับหรือล้มเหลว — ทยอยมาตามที่แต่ละหน่วยงานเสร็จ ไม่ตามลำดับ และไม่รอตัวอื่น

```json
{
  "agency_id": "019d5cf7-9dcf-7aa5-bc3e-21ba67822923",
  "agency_name": "กรมที่ดิน",
  "status": "ok",
  "section_label": "โอนที่ดิน",
  "error_type": null
}
```

| ฟิลด์ | ชนิด | คำอธิบาย |
|---|---|---|
| `agency_id` | string | รหัสหน่วยงาน |
| `agency_name` | string \| null | ชื่อหน่วยงาน |
| `status` | enum | `ok` = หน่วยงานตอบกลับสำเร็จ / `error` = ล้มเหลว |
| `section_label` | string \| null | หัวข้อย่อยที่สังกัด |
| `error_type` | string \| null | ชนิดข้อผิดพลาด เช่น `TimeoutError`, `CircuitOpenError` (มีค่าเมื่อ `status = error`) |

หน่วยงานที่ `status = error` จะไม่มี event `agency_verified` ตามมา (ขั้น verify ข้ามตัวที่ล้มเหลว)

---

### `agency_verified` — ผลตรวจความเกี่ยวข้อง (จากขั้น verify)

ส่ง 1 ครั้งต่อหน่วยงานที่ `agency_responded` ด้วย `status = ok` — เป็นคำตัดสินสุดท้ายของหน่วยงานนั้น

```json
{
  "agency_id": "019d5cf7-9dcf-7aa5-bc3e-21ba67822923",
  "agency_name": "กรมที่ดิน",
  "status": "passed",
  "relevance_score": 1.0,
  "section_label": "โอนที่ดิน"
}
```

| ฟิลด์ | ชนิด | คำอธิบาย |
|---|---|---|
| `agency_id` | string | รหัสหน่วยงาน |
| `agency_name` | string \| null | ชื่อหน่วยงาน |
| `status` | enum | `passed` = คำตอบผ่าน จะถูกใช้ใน `answer` / `rejected` = ไม่เกี่ยวข้อง ถูกตัดทิ้ง |
| `relevance_score` | number \| null | คะแนนความเกี่ยวข้อง 0–1 |
| `section_label` | string \| null | หัวข้อย่อยที่สังกัด |

วงจรชีวิตของหน่วยงานหนึ่ง:

```
สำเร็จ:  agency_start -> agency_responded(ok) -> agency_verified(passed | rejected)
ล้มเหลว: agency_start -> agency_responded(error)
```

หมายเหตุ: `agency_responded` ของแต่ละหน่วยงานส่งทันทีไม่รอกัน แต่ช่วงเวลาจาก `agency_responded` ถึง `agency_verified` ของหน่วยงานเดียวกันจะรอจนหน่วยงานช้าสุดตอบครบ เพราะขั้น verify เริ่มทำงานหลังขั้น invoke จบทั้งหมด

---

### `answer` — คำตอบสุดท้าย

ข้อมูลชุดเดียวกับ `ChatV3Data` (field `data` ใน response ของ `/v3/chat`)

```json
{
  "answer": "## โอนที่ดิน\n\n**กรมที่ดิน**\n\nสวัสดีค่ะ สำหรับขั้นตอน...",
  "sections": [
    {
      "title": "โอนที่ดิน",
      "agencies": [
        {
          "id": "019d5cf7-9dcf-7aa5-bc3e-21ba67822923",
          "name": "กรมที่ดิน",
          "query": "ต้องการโอนที่ดิน...",
          "content": "สวัสดีค่ะ สำหรับขั้นตอนการโอนที่ดิน..."
        }
      ]
    }
  ],
  "errors": [
    {
      "agency": "019d5cf7-9dc4-70e0-b4a5-3f549d0cf7b9",
      "name": "กรมการปกครอง",
      "errorType": "TimeoutError",
      "message": "agency timed out after 60000 ms"
    }
  ],
  "debug": { "...": "ดูด้านล่าง" }
}
```

| ฟิลด์ | ชนิด | คำอธิบาย |
|---|---|---|
| `answer` | string | คำตอบสุดท้ายเป็น Markdown — ฟิลด์หลักที่ใช้แสดงผล |
| `sections` | array | คำตอบแยกตามหัวข้อย่อย (ก่อนเรียบเรียง) ใช้แสดงแบบ structured ได้ |
| `sections[].title` | string | ชื่อหัวข้อ (= `section_label`) |
| `sections[].agencies[]` | array | คำตอบดิบของแต่ละหน่วยงานในหัวข้อนั้น (`id`, `name`, `query`, `content`) |
| `errors` | array | หน่วยงานที่ล้มเหลว (`agency` = id, `name`, `errorType`, `message`) |
| `debug` | object \| null | ข้อมูล debug ของทั้ง request (ดูด้านล่าง) |

ถ้าไม่มีคำตอบที่เกี่ยวข้องเลย `answer` จะเป็นข้อความ fallback เช่น
`"ขออภัย ไม่พบคำตอบที่เกี่ยวข้อง กรุณาลองใหม่อีกครั้ง หรือติดต่อหน่วยงานโดยตรง"` และ `sections` จะเป็น `[]`

โครงสร้าง `debug` (สำหรับหน้า debug/dev เท่านั้น):

| ฟิลด์ | ชนิด | คำอธิบาย |
|---|---|---|
| `intent` | string | intent ที่จัด |
| `query` | string | คำถามดิบ |
| `normalized_query` | string \| null | คำถามที่ปรับแล้ว |
| `history_turns` | number | จำนวน turn ของประวัติที่ใช้ |
| `reasoning` | string | เหตุผลการจัดประเภท |
| `discovered_agencies[]` | array | หน่วยงานที่ค้นพบ (`id`, `name`, `description`, `data_scope`) |
| `sub_questions[]` | array | การแตกคำถาม + routing + ผลต่อหน่วยงาน (ดูตารางถัดไป) |
| `passed_count` | number | จำนวนคำตอบที่ผ่าน |
| `rejected_count` | number | จำนวนคำตอบที่ถูกตัดเพราะไม่เกี่ยวข้อง |
| `error_count` | number | จำนวนหน่วยงานที่ล้มเหลว |
| `fallback_used` | boolean | `true` ถ้าไม่มีคำตอบผ่านเลย |
| `timings` | object | `intent_ms`, `mcp_discovery_ms`, `invoke_ms`, `verify_ms` |

แต่ละรายการใน `debug.sub_questions[]`:

| ฟิลด์ | ชนิด | คำอธิบาย |
|---|---|---|
| `section_label` | string | ชื่อหัวข้อย่อย |
| `original_query` | string | คำถามดิบของผู้ใช้ |
| `confidence` | number \| null | ความมั่นใจของ LLM ในการ routing |
| `broadcast` | boolean | ถามทุกหน่วยงานหรือเจาะจง |
| `broadcast_reason` | string \| null | `no_match` / `low_confidence` / `classify_failed` / `null` |
| `suggested_agencies` | string[] | agency_id ที่ LLM แนะนำ |
| `selected_agencies` | string[] | agency_id ที่ถูกเรียกจริง |
| `results[]` | array | ผลต่อหน่วยงาน: `agency_id`, `agency_name`, `query_sent`, `status`, `relevance_score`, `raw_answer`, `error_type`, `error_message`, `response_time_ms`, `retry_count` |

---

### `done` — จบ stream

event สุดท้ายเสมอ หลังจากนี้ server ปิด connection

```json
{ "session_id": "f4ea61cc-47ac-4e46-bd6c-9cadc54ba999", "total_ms": 66351 }
```

| ฟิลด์ | ชนิด | คำอธิบาย |
|---|---|---|
| `session_id` | string | session ID ของ request นี้ — เก็บไว้ส่งกลับใน request ถัดไปเพื่อให้จำประวัติได้ |
| `total_ms` | number | เวลารวมทั้ง request (มิลลิวินาที) |

---

### `error` — ข้อผิดพลาดร้ายแรง (reserved)

```json
{ "message": "...", "code": 500 }
```

สถานะปัจจุบัน: ขั้นตอนต่าง ๆ ใน pipeline ดักจับ error ของตัวเองไว้หมดแล้ว (MCP ล่ม จะได้ `agencies.count = 0`, หน่วยงาน error จะเข้า `agency_responded.status = "error"` และ `answer.errors`) event `error` จึงแทบไม่ถูกส่งในทางปฏิบัติ หากเกิดข้อผิดพลาดที่ดักไม่ได้จริง ๆ connection จะถูกตัดโดยไม่มี `done` ดังนั้นอย่ารอ `error` เป็นสัญญาณหลัก ให้ใช้เกณฑ์ "stream ปิดโดยไม่มี `done`" แทน (ดูข้อ 8)

---

## 7. แนวทางจัดการ state ฝั่ง Frontend

แนะนำให้เก็บ state กลางเป็น object เดียว แล้วอัปเดตตาม event ที่เข้ามา:

| ส่วนของ state | อัปเดตจาก event | วิธีอัปเดต |
|---|---|---|
| ขั้นตอนปัจจุบัน | `step` (`status: running`) | บันทึกชื่อขั้นล่าสุด |
| สถานะแต่ละขั้น | `step` | เก็บ map ของ `name` -> `running`/`done` |
| รายชื่อหน่วยงาน | `agencies` | แทนที่ทั้งชุด |
| intent / routing | `intent`, `routing` | แทนที่ |
| สถานะรายหน่วยงาน | `agency_start`, `agency_responded`, `agency_verified` | เก็บ map key ด้วย `agency_id` แล้วเขียนทับทุกครั้ง |
| คำตอบสุดท้าย | `answer` | แทนที่ |
| จบหรือยัง | `done` | ตั้ง flag เป็น true |

จุดสำคัญ:
- หน่วยงานหนึ่งมีลำดับ `agency_start` -> `agency_responded` -> `agency_verified` อ้างอิงด้วย `agency_id` แล้วเขียนทับสถานะเดิมเสมอ ห้ามเก็บแบบ append เข้า array
- `agency_start` มาก่อน ใช้สร้าง entry สถานะ "กำลังรอ" ไว้รอ
- หน่วยงานที่ `agency_responded` ด้วย `status = error` จะไม่มี `agency_verified` ตามมา
- ใช้ event `step` คุม UI progress bar / spinner ของแต่ละขั้น

---

## 8. การจัดการข้อผิดพลาด

| สถานการณ์ | สิ่งที่เกิดขึ้น | ฝั่ง Frontend ควรทำ |
|---|---|---|
| Request ผิด (ขาด field / field เกิน) | HTTP `400` พร้อม JSON `{"error": "..."}` ก่อนเปิด stream | ตรวจ HTTP status ก่อนอ่าน stream |
| MCP catalog ล่ม / discover ไม่เจอ | stream ทำงานปกติ แต่ `agencies.count = 0` และ `answer` เป็นข้อความ fallback | แสดงข้อความว่าไม่พบหน่วยงาน |
| หน่วยงานหนึ่ง timeout / error | `agency_responded.status = "error"` และอยู่ใน `answer.errors` (หน่วยงานอื่นยังทำงานต่อ) | แสดง error เฉพาะหน่วยงานนั้น |
| Server error ที่ดักไม่ได้ | connection ถูกตัด ไม่มี event `done` | เช็ค flag "ได้ `done` หรือยัง" — ถ้าไม่ได้ ถือว่า error |
| ผู้ใช้กดยกเลิก | — | ยกเลิก request (เช่น ผ่าน `AbortController`) |

กฎทอง: ความสำเร็จของ request วัดจากการได้รับ event `done` ไม่ใช่แค่ stream ปิด

---

## 9. หมายเหตุด้านประสิทธิภาพ

- pipeline ทั้งหมดใช้เวลาทั่วไป ~30–90 วินาที ขึ้นกับความเร็วของหน่วยงานปลายทาง — ตั้ง timeout ฝั่ง client ให้ยาวพอ (แนะนำอย่างน้อย 120 วินาที) หรือไม่ตั้งเลยแล้วใช้กลไกยกเลิก request แทน
- ขั้น `invoke` นานสุด หน่วยงานเป็น LLM agent ตอบช้า (เคยวัดได้ ~43 วินาทีสำหรับคำตอบที่ถูกต้อง) timeout ต่อหน่วยงานคือ ~60 วินาที
- หน่วยงานถูกเรียกพร้อมกันทุกตัว ขั้น `invoke` จึงจบเมื่อหน่วยงานช้าสุดเสร็จ
- ใช้ event `step` ร่วมกับ `agency_start`/`agency_responded`/`agency_verified` แสดง progress ละเอียดเพื่อไม่ให้ผู้ใช้รู้สึกว่าค้าง
- header `X-Accel-Buffering: no` ถูกตั้งให้แล้ว ถ้าเว็บอยู่หลัง reverse proxy (nginx ฯลฯ) ต้องไม่ buffer response ของ endpoint นี้

---

## ภาคผนวก — สรุป event ทั้งหมด

| event | ส่งเมื่อ | จำนวนครั้งต่อ request |
|---|---|---|
| `step` | เริ่ม/จบแต่ละขั้น | 2 ครั้ง/ขั้น (running + done) |
| `agencies` | discover เสร็จ | 1 |
| `intent` | classify เสร็จ | 1 |
| `routing` | classify เสร็จ (เฉพาะ `search`) | 0–1 |
| `agency_start` | เริ่ม invoke | 1 ครั้ง/หน่วยงาน |
| `agency_responded` | หน่วยงานตอบกลับหรือล้มเหลว | 1 ครั้ง/หน่วยงาน |
| `agency_verified` | ผลตรวจความเกี่ยวข้องเสร็จ | 0–1 ครั้ง/หน่วยงาน (ไม่มีถ้า responded = error) |
| `answer` | synthesize เสร็จ | 1 |
| `done` | จบ stream | 1 (event สุดท้าย) |
| `error` | ข้อผิดพลาดร้ายแรง | 0 (แทบไม่เกิด — ดูข้อ 6/8) |
