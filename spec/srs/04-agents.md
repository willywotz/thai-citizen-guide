# SRS — 04: LLM Tasks & Agency Adapters

← [ดัชนี](README.md)

---

> เอกสารนี้สะท้อนสถานะโค้ดปัจจุบัน · flow ภายในดู [02-architecture.md](02-architecture.md)

OneChat ใช้ LLM ผ่าน **`MultiplexedLLMClient`** (provider เป็น vLLM หรือ OpenRouter, เลือก/ตั้ง main+fallback ได้ runtime) สำหรับงาน 6 ชนิด และเชื่อมต่อหน่วยงานปลายทางผ่าน **agency adapter** เอกสารนี้อธิบายทั้งสองส่วน

- คำว่า **"LLM task"** = การเรียก LLM provider ที่ตั้งค่าไว้เพื่อทำงานเฉพาะอย่าง (มี 6 ชนิด)
- คำว่า **"agency"** = หน่วยงานภาครัฐปลายทาง (เป็น HTTP service ภายนอก มักเป็น Dify LLM agent) — OneChat เรียกผ่าน adapter

LLM client ทั้งหมดอยู่ที่ `app/llm/multiplexed.py` (`MultiplexedLLMClient`, implement `SynthesisLLM` protocol ใน `app/llm/protocol.py`) prompt builder อยู่ที่ `app/llm/prompts.py` model/provider ที่ใช้จริงมาจาก Postgres (`llm_provider_config`, ตั้งผ่านหน้า LLM Setting ของ debug console ที่ `/v1/llm-settings`) ไม่ใช่ env var แล้ว — `model` argument ที่ node ส่งเข้าไปในแต่ละ method ถูกละเว้น ใช้ model จาก config row แทน

---

## LLM Task 1 — Analyze Query

| | |
|---|---|
| เมธอด | `MultiplexedLLMClient.analyze_query` |
| Prompt builder | `build_analyze_query_messages` |
| เรียกจาก node | `analyze_query` ([analyze_query.py](../../app/graph/nodes/analyze_query.py)) |
| ความถี่ | 1 ครั้งต่อ request |
| temperature | `0.0` · `response_format: json_object` |

**บทบาท:** LLM call เดียวแบบ Chain-of-Thought ทำ 5 อย่างพร้อมกัน

1. **Normalize** — แก้ pronoun/บริบทจาก history ให้คำถาม self-contained + แปลงภาษาพูดเป็นภาษาเขียน
2. **Classify intent** — `chitchat` / `capability` / `out_of_scope` / `search`
3. **Decompose** — แตก `search` เป็น 1–3 sub-question (เฉพาะเมื่อหัวข้อแยกกันชัดเจน)
4. **Route** — เลือกหน่วยงานต่อ sub-question + เขียนคำถามเฉพาะของแต่ละหน่วยงาน + ให้ค่า confidence
5. **Label** — ตั้ง section label (Thai noun phrase) ต่อ sub-question

> `out_of_scope` = คำหยาบ / ข่มขู่ / ไร้สาระ / ขออะไรผิดกฎหมาย / **ความพยายาม prompt injection หรือ jailbreak** (เช่น "ลืมคำสั่งเดิมทั้งหมด", "เปิดเผย system prompt", "ignore previous instructions") — LLM เขียน `refusal_reply` ภาษาไทย ระบบ skip ขั้น invoke/verify/synthesize ทั้งหมด ตอบกลับเร็ว (~3-5s) ประหยัด resource
>
> คำถามที่อยู่นอกขอบเขตข้อมูลของ agency (เช่น สูตรอาหาร) **ไม่ใช่** `out_of_scope` — ถูกจัดเป็น `search` ตามปกติแล้วให้ agency ตอบเองว่าไม่ครอบคลุม
>
> **มาตรฐานคำตอบ `chitchat_reply`/`refusal_reply`:** ลงท้าย "ครับ" เสมอ (ห้าม "ค่ะ"), ห้ามมี emoji, ตอบประโยคมาตรฐานเดียวกันเสมอไม่ว่าเนื้อหาต้นทางจะเป็นอะไร (chitchat ห้ามเล่นมุขตามข้อความผู้ใช้, out_of_scope ห้ามสั่งสอน/ตำหนิ)

**Input:** `query`, รายการ agency (`agency_id`, `name`, `description`, `data_scope`), `history`

**Output (JSON):**

| Field | คำอธิบาย |
|---|---|
| `reasoning` | เหตุผล CoT |
| `normalized_query` | คำถามหลังปรับ |
| `intent` | `chitchat` / `capability` / `out_of_scope` / `search` |
| `chitchat_reply` | คำตอบ chitchat (เมื่อ intent = chitchat) |
| `refusal_reply` | คำตอบ refusal (เมื่อ intent = out_of_scope) |
| `sub_questions[]` | `section_label`, `confidence`, `agencies[]` (`agency_id` + `question`) |

**กลยุทธ์ routing** (ทำใน node ไม่ใช่ LLM):

| confidence | ผล |
|---|---|
| 0.95–1.0 | data_scope ตรงกับคำถามโดยตรง ไม่มีหน่วยงานอื่นใกล้เคียงเท่ากัน |
| 0.7–0.85 | น่าจะตรง แต่มีหน่วยงานอื่นที่ data_scope ใกล้เคียงพอจะครอบคลุมได้เช่นกัน |
| 0.4–0.6 | ไม่แน่ใจว่าหน่วยงานนี้ตรงกับคำถามหรือไม่ |
| 0.0–0.3 | คำถามกว้าง/คลุมเครือมาก จนไม่มีหน่วยงานไหนตรงชัดเจนกว่าหน่วยงานอื่น |
| **≥ 0.9** | **(threshold ที่ระบบใช้จริง)** ส่งคำถามเฉพาะหน่วยงานที่ LLM เลือก (`broadcast = false`) |
| **< 0.9** | **(threshold ที่ระบบใช้จริง)** broadcast `normalized_query` ไปทุกหน่วยงาน (`broadcast = true`) |

**เมื่อ LLM ล้มเหลว:** `analyze_query` **ไม่ degrade เงียบ ๆ อีกต่อไป** — exception จาก LLM ถูก raise ตรงออกไป (เหมือนพฤติกรรมเดิมของ `generate_markdown`) เดิมเคยคืน fallback dict `intent = search` แบบ broadcast ทุกหน่วยงานเงียบ ๆ ซึ่งพบว่าทำให้ทุกคำถาม (รวมทักทายธรรมดา) ยิงไปทุก agency โดยผู้ใช้ไม่รู้ตัวว่า LLM ใช้งานไม่ได้ — เปลี่ยนเป็น fail loud แทน

> ถ้าสร้าง node โดยไม่มี `llm_client` (test เท่านั้น) จะ broadcast ทุกหน่วยงานโดยไม่เรียก LLM

---

## LLM Task 2 — Verify Relevance

| | |
|---|---|
| เมธอด | `MultiplexedLLMClient.verify_relevance` |
| Prompt builder | `build_verify_relevance_messages` |
| เรียกจาก node | `verify_relevance` ([verify.py](../../app/graph/nodes/verify.py)) |
| ความถี่ | 1 ครั้งต่อคำตอบหน่วยงานที่ไม่ error (ขนานด้วย `asyncio.gather`) |
| temperature | `0.0` · `response_format: json_object` |

**บทบาท:** ให้คะแนนว่าคำตอบของหน่วยงานตอบตรงคำถามจริงไหม กัน redirect / คำตอบนอกเรื่องไม่ให้หลุดไปถึงผู้ใช้

**Input:** `query` (คำถามที่ส่งไปหน่วยงานนั้น), `answer` (คำตอบดิบ)

**Output:** `relevance_score` — float `0.0–1.0`

**เกณฑ์คะแนน** (กำหนดใน prompt):

| คะแนน | ความหมาย |
|---|---|
| 0.3 | นอกเรื่อง หรือ redirect ไปหน่วยงาน/เว็บอื่น |
| 0.6 | ตอบบางส่วน / ลิงก์ไปหน้าของหน่วยงานตัวเองแต่ไม่ครบ |
| 0.8 | ตอบตรง มีขั้นตอน/ข้อกำหนดจากหน่วยงานนี้ |
| 1.0 | ตอบครบถ้วน นำไปใช้ได้ทันที |

**การตัดสิน** (ทำใน node): `score > 0.5` = ผ่าน; `score ≤ 0.5` = ตั้ง `error = "RelevanceError: ..."` คำตอบนั้นถูกตัดออกจาก section

**เมื่อ LLM ล้มเหลว:** คืน `0.0` (fail-closed — ทั้งใน `MultiplexedLLMClient` และใน node `verify.py` เป็น fallback ซ้อนกันสองชั้น) คะแนน 0.0 ต่ำกว่า threshold แน่นอน = ไม่ผ่านเสมอ เดิมเคย fallback เป็น `0.6` ซึ่งอยู่ *เหนือ* threshold `> 0.5` — แปลว่า "ตรวจสอบไม่ได้" เคยถูกนับเป็น "ผ่านการตรวจสอบ" เงียบ ๆ โดยไม่ตั้งใจ แก้เป็น fail-closed แล้ว

---

## LLM Task 3 — Generate Markdown (v1 เท่านั้น)

| | |
|---|---|
| เมธอด | `MultiplexedLLMClient.generate_markdown` |
| Prompt builder | `build_generate_markdown_messages` |
| เรียกจาก node | `synthesize_answer` ([synthesize.py](../../app/graph/nodes/synthesize.py)) |
| ความถี่ | 1 ครั้งต่อ request (เฉพาะกราฟ v1) |
| temperature | `0.2` |

**บทบาท:** รวมคำตอบจากหลายหน่วยงานเป็นคำตอบ Markdown เดียวที่อ่านลื่น

**Input:** `query`, `successful_results` (คำตอบที่ผ่าน verify), `language` (จาก `DEFAULT_LANGUAGE`), `history`

**Output:** Markdown string

**กฎใน prompt:** ใช้เฉพาะหลักฐานจากหน่วยงาน, ห้ามเติมข้อมูลเอง, ถ้าหน่วยงานขัดแย้งให้ระบุชัด, รวมให้กลมกลืนไม่ใช่ต่อกันดิบ ๆ

**เมื่อ LLM ล้มเหลว:** `synthesize_answer` จับ exception → คืนข้อความ fallback + `AgencyErrorDetail` ชนิด `LLMGenerationError`, `answer_synthesized = false`

> v2/v3/v4/v5 **ไม่ใช้** task นี้ — v3/v4/v5 นำ raw answer มาต่อกันเองใน `format_v3_response`/`format_v5_response` (ผ่าน helper กลาง `section_builder.py`) โดยไม่เรียก LLM เลย — v5 เพิ่มบทสรุปภาพรวมแยกต่างหากไว้บนสุดผ่าน task 4 ด้านล่าง แต่เนื้อหา section เองยังไม่เรียก LLM เหมือนเดิม

> **เรื่อง session กับ agency:** prompt บอกว่า "Agencies have NO memory — each question must be fully self-contained" — กลยุทธ์หลักคือ rewrite คำถามให้ครบบริบทเสมอ session_id ที่ส่งให้ agency (ดู `request_session_field`) เป็นสัญญาณเสริม agency ตัวที่ใช้ session ฝั่งตัวเองจะ map turn ต่อกันได้ ส่วน agency ที่ไม่สนใจ session ก็ยังตอบถูกเพราะคำถามครบบริบทอยู่แล้ว

---

## LLM Task 4 — Generate Executive Summary (v5 เท่านั้น)

| | |
|---|---|
| เมธอด | `MultiplexedLLMClient.generate_executive_summary` |
| Prompt builder | `build_executive_summary_messages` |
| เรียกจาก node | `summarize_answer` ([summarize.py](../../app/graph/nodes/summarize.py)) |
| ความถี่ | **1 ครั้งต่อ request ทั้งหมด** (ไม่ใช่ต่อ agency) — เฉพาะเมื่อมี ≥1 agency ผ่าน verify |
| temperature | `0.2` |
| response format | `json_object` — คืน `{summary: "..."}` |

**บทบาท:** เขียนบทสรุปภาพรวมสั้นๆ พร้อมเลขอ้างอิง `[n]` กำกับทุกข้อเท็จจริงสำคัญ จาก agency **ทุกตัวที่ผ่าน verify ในทั้ง request** (ไม่ใช่แค่หัวข้อเดียว) — สิ่งนี้เข้ามาแทนกลไก trim/connect เดิมทั้งคู่ (v5 เก่าตัด filler ต่อ agency + แต่งประโยคเชื่อมต่อหัวข้อ) ด้วยการเพิ่มบทสรุปแยกไว้บนสุดแทน ส่วนเนื้อหา section ด้านล่างกลับไปเป็น raw content เหมือน v4 ทุกประการ

**เลขอ้างอิงกำหนดโดยโค้ด ไม่ใช่ LLM:** node `summarize_answer` dedupe agency ที่ผ่าน verify ต่อ agency ตลอดทั้ง request (agency เดียวตอบ 2 หัวข้อได้เลขอ้างอิง**เดียว**) แล้วเรียงเป็น numbered list ส่งเข้า prompt — LLM แค่ใส่ `[n]` อ้างอิงเลขที่ให้มา ไม่ได้เป็นคนกำหนดเลขเอง `references[]` จึงสร้างจากโค้ดตรงๆ ไม่มีการ parse เลขจากผลลัพธ์ LLM

**เมื่อ LLM ล้มเหลวหรือ output ผิดรูปแบบ:** degrade เงียบ — `summary`/`references` เป็นค่าว่าง `answer` กลายเป็น v4-identical (ไม่มีบทสรุป ไม่มี `---` คั่นค้าง) node ยัง scrub เลข `[n]` ที่ LLM อ้างเกินขอบเขตรายการที่ให้ไปทิ้งเสมอ (ป้องกันเลขหลอน ไม่ใช่การอนุมานความหมายจากผลลัพธ์)

---

## LLM Task 5 — Synthesize No-Answer (v3/v4/v5)

| | |
|---|---|
| เมธอด | `MultiplexedLLMClient.synthesize_no_answer` |
| Prompt builder | `build_no_answer_synthesis_messages` |
| เรียกจาก node | `build_no_answer_message` ([fallback_message.py](../../app/graph/nodes/fallback_message.py)) |
| ความถี่ | 1 ครั้ง เมื่อมี agency ที่ไม่ผ่าน verify ตั้งแต่ 2 รายขึ้นไปในหัวข้อ/request เดียวกัน |
| temperature | `0.2` |
| response format | `json_object` — คืน `{intro, summaries[]}` |

**บทบาท:** เมื่อไม่มี agency ไหนตอบตรงประเด็นเลย (ทั้งระดับ sub-question เดียวหรือทั้ง request) สังเคราะห์ข้อความเดียวจากคำตอบจริงของทุก agency (หรือ `data_scope` แทนถ้า agency นั้น error จนไม่มีคำตอบ) ระบุชัดว่าใครช่วยไม่ได้และแต่ละหน่วยงานให้ข้อมูลอะไรได้บ้างแทน

**สไตล์ (เพิ่มใหม่, แคบกว่า chitchat/out_of_scope โดยตั้งใจ):** `intro` ต้องลงท้าย "ครับ" เสมอ ห้ามมี emoji — แต่เนื้อหายัง**ต้องแตกต่างกันในแต่ละครั้ง** (สรุป agency ที่ต่างกันจริง) จึงไม่ใช้กฎ "ประโยคเดียวกันเสมอ" แบบ chitchat/out_of_scope

**ข้อควรรู้:** โค้ด (ไม่ใช่ LLM) เป็นคนประกอบ `intro` + summaries เข้าด้วยกันด้วย `---` คั่นเสมอ — กันปัญหาที่ LLM เขียน markdown เองแล้วบางครั้งลืมใส่ตัวคั่น ถ้า LLM คืนรูปแบบผิด (จำนวน summary ไม่ตรงกับจำนวน agency) fallback เป็นข้อความต่อ block ตรงๆ ไม่มี LLM แต่ง

**กรณี agency เดียวไม่ผ่าน** ไม่เรียก task นี้ — ใช้คำตอบจริงของ agency นั้นตรงๆ ไม่มีการตัดแต่งใดๆ อีกต่อไป (ทั้ง v3/v4/v5 เหมือนกันหมดตั้งแต่ลบกลไก trim ออก)

---

## สรุป LLM call ต่อ request

| Endpoint | analyze_query | verify_relevance | generate_markdown | generate_executive_summary | synthesize_no_answer | รวม (ทั่วไป) |
|---|---|---|---|---|---|---|
| v1 | 1 | N | 1 | 0 | 0 | `2 + N` |
| v2 / v3 / v4 | 1 | N | 0 | 0 | 0–1 | `1 + N` (+1 ถ้า fallback) |
| v5 | 1 | N | 0 | 0–1 | 0–1 | `1 + N` (+1 ถ้ามี agency ผ่าน verify, +1 ถ้า fallback) |

N = จำนวนคำตอบหน่วยงานที่ไม่ error, M = จำนวนหัวข้อที่มี agency ผ่าน ≥ 2 ราย (chitchat/capability ข้าม invoke/verify ทั้งหมด)

---

## Agency Adapters

หน่วยงานปลายทางเชื่อมผ่าน adapter interface เดียว ทำให้ orchestrator ไม่ต้องรู้รายละเอียด HTTP ของแต่ละหน่วยงาน

### `AgencyAdapter` (ABC)

[`app/adapters/base.py`](../../app/adapters/base.py) — สัญญาเดียว:

```python
async def call(self, query: str) -> AgencyResult
```

`AgencyResult` (dataclass): `agency_id`, `raw_answer`, `references`, `error`, `relevance_score`, `query_used`, `response_time_ms`, `retry_count`

### `GenericAdapter`

[`app/adapters/generic.py`](../../app/adapters/generic.py) — adapter จริงที่ใช้ production แมป REST แบบ config-driven จาก `AgencyConfig`:

| ด้าน | กลไก |
|---|---|
| Request | GET (query params) หรือ POST (JSON body) ตาม `request_method` |
| Query field | ใส่ `query` ลง path ของ `request_query_field` (รองรับ dotted path) |
| Session field | ใส่ OneChat session_id ลง path ของ `request_session_field` — detection: ชื่อฟิลด์ `session_id`/`conversation_id`/`thread_id` สำหรับ agency ทั่วไป, หรือ `user` สำหรับ Dify-style (รวมที่ proxy ผ่าน URL อื่น เช่น `/agent-proxy/<uuid>` — detect จากการมี `user`+`inputs`+`response_mode` ใน expected_payload) |
| Status filter | MCP catalog ตอนนี้คืน `status: "active" | "maintenance" | ...` ต่อ agency → map เป็น `AgencyConfig.enabled` (active=True, อื่น ๆ =False) → `analyze_query` กรองตัว disabled ออกจาก routing เอง |
| URL normalisation | `HttpMCPCatalogClient` เติม `/` ท้าย `mcp_endpoint_url` อัตโนมัติเพื่อกัน 307 redirect ที่ทำให้ fastmcp session lifecycle ค้าง |
| Static payload | merge `request_static_payload` เข้า body |
| Auth | `auth_type` = `bearer` / `api_key` / `none`; secret อ่านจาก env var ชื่อ `auth_secret_env` |
| Headers | `api_headers` จาก MCP catalog |
| Response | สกัดคำตอบ/อ้างอิงด้วย dotted path `response_answer_path` / `response_references_path` พร้อม fallback หลายชั้น |
| Timeout | `httpx` timeout = `timeout_ms` (ค่าเริ่มต้น 60000) |

**การจัดการ error:** timeout (`httpx.TimeoutException`) ถูก raise ออกไปให้ `invoke.py` จัดการ; HTTP error / JSON error อื่นถูกแปลงเป็น `AgencyResult.error` (ไม่ raise)

### `MockAgencyAdapter`

[`app/adapters/mock.py`](../../app/adapters/mock.py) — คืนคำตอบคงที่ ใช้ใน test

### การ resolve เป็น adapter

`adapter_factory` (inject ผ่าน `OrchestratorDependencies`) สร้าง `GenericAdapter` จาก `AgencyConfig` ที่ได้จาก MCP discovery — ดูการ map MCP item → `AgencyConfig` ใน `app/services/mcp_catalog.py`

### Reliability รอบการเรียก agency

`_invoke_single_agency` ใน [`invoke.py`](../../app/graph/nodes/invoke.py) ห่อ `adapter.call()` ด้วย:

1. `circuit_breaker.allow()` — ถ้า circuit เปิดอยู่ → `CircuitOpenError` ทันที
2. `AsyncRetrying` (tenacity, exponential jitter) — retry **เฉพาะ `RuntimeError`** ไม่ retry timeout
3. `asyncio.wait_for(..., timeout)` — ตัดที่ `timeout_ms`

ทุกหน่วยงานถูกเรียกขนานด้วย `asyncio.as_completed` — หน่วยงานที่ตอบก่อนได้ event ก่อน (สำคัญสำหรับ v4 streaming)

---

## เอกสารที่เกี่ยวข้อง

- [02-architecture.md](02-architecture.md) — node graph และ flow
- [03-api.md](03-api.md) / [../api/](../api/) — endpoint และ schema ทั้ง 5 เวอร์ชัน
- [07-mcp-spec.md](07-mcp-spec.md) — สัญญาสำหรับผู้พัฒนา MCP server
- [06-bugs.md](06-bugs.md) — ปัญหาที่รู้อยู่ (รวม config ที่ไม่ถูกใช้)
