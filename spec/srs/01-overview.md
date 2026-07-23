# SRS — 01: ภาพรวมระบบ

← [ดัชนี](README.md)

---

> เอกสารชุดนี้สะท้อนสถานะโค้ดปัจจุบัน ดู [README.md](README.md) สำหรับสารบัญทั้งหมด

## OneChat คืออะไร

OneChat เป็น **backend orchestrator** ที่รับคำถามภาษาไทยจากผู้ใช้ แล้วกระจายไปถามหน่วยงานภาครัฐหลายแห่งพร้อมกัน จากนั้นรวบรวมคำตอบกลับมาเป็นคำตอบเดียว

จุดเด่นคือ **ไม่มีฐานข้อมูลรายชื่อหน่วยงานของตัวเอง** — ทุก request จะค้นหาหน่วยงานที่ใช้ได้สด ๆ จาก MCP catalog endpoint ที่ client ส่งมาในแต่ละครั้ง ระบบจึงไม่ผูกกับชุดหน่วยงานตายตัว

## ทำงานอย่างไร (ระดับสูง)

```
ผู้ใช้ถาม → ค้นหาหน่วยงานจาก MCP → LLM วิเคราะห์+แตกคำถาม → ยิงถามหน่วยงานพร้อมกัน
         → LLM ตรวจความเกี่ยวข้อง → เรียบเรียงคำตอบ → ส่งกลับ
```

รายละเอียดเต็มดู [02-architecture.md](02-architecture.md)

## ขอบเขต (Scope)

| อยู่ในขอบเขต | ไม่อยู่ในขอบเขต |
|---|---|
| รับคำถาม กระจายไปหน่วยงาน รวมคำตอบ | จัดเก็บ/เป็นเจ้าของข้อมูลของหน่วยงาน |
| ค้นหาหน่วยงานแบบ runtime ผ่าน MCP | UI / frontend (เป็น backend API ล้วน) |
| จัดประเภทคำถาม + แตกคำถามย่อย + จัด routing | ระบบ authentication ของผู้ใช้ปลายทาง |
| ตรวจความเกี่ยวข้องของคำตอบด้วย LLM | คิวงาน / การประมวลผลแบบ batch |
| ประวัติการสนทนาแบบ session (ถ้ามี Redis) | ฐานข้อมูลถาวรของบทสนทนา |
| 5 รูปแบบ response (v1–v5) | — |

## API 5 เวอร์ชัน

ทุกเวอร์ชันรับ request body เดียวกัน ต่างกันที่รูปแบบคำตอบ

| Endpoint | คำตอบ | LLM synthesis |
|---|---|---|
| `POST /v1/chat` | Markdown เดียวที่ LLM เรียบเรียงรวม | ใช่ |
| `POST /v2/chat` | คำตอบดิบแยกรายหน่วยงาน | ไม่ |
| `POST /v3/chat` | คำตอบแยกเป็น section ต่อหัวข้อ + debug | ไม่ |
| `POST /v4/chat` | เหมือน v3 แต่ streaming แบบ SSE ตามขั้นตอน | ไม่ |
| `POST /v5/chat` | เหมือน v4 + บทสรุปภาพรวมพร้อม inline citation ไว้บนสุด + thread name | ไม่ (เฉพาะเนื้อหา agency; บทสรุปเป็นเนื้อหาแยกต่างหาก ไม่ปนใน section) |

รายละเอียดดู [03-api.md](03-api.md)

## ข้อจำกัดหลัก (Constraints)

ข้อจำกัดเหล่านี้เป็นกฎที่โค้ดยึดถือ ห้ามละเมิด:

- **Stateless** — ไม่เก็บ state ของบทสนทนาข้าม request ใน process; ทุก request สร้าง state ใหม่หมด (ประวัติเก็บแยกใน Redis)
- **เรียกหน่วยงานแบบขนานเท่านั้น** — ห้าม serialize การเรียก agency
- **Secret ผ่าน environment variable เท่านั้น** — `auth_secret_env` เก็บ*ชื่อ* env var ไม่ใช่ค่า secret
- **Response schema ต้องตรงกับ** [openapi.yaml](../api/openapi.yaml) — มี test บังคับ (`tests/test_openapi_compliance.py`)
- **MCP-first สำหรับหน่วยงาน** — ไม่มี database ของหน่วยงาน ทุกอย่าง discover ตอน runtime (Postgres มีจริงแต่ใช้เก็บแค่ LLM provider config + cost log เท่านั้น ไม่เกี่ยวกับหน่วยงาน)
- **หน่วยงานล่มต้องไม่ทำให้ทั้ง request ล้ม** — error ถูกบันทึกเป็น `AgencyErrorDetail` และ pipeline เดินต่อ

## Tech stack โดยย่อ

| ด้าน | เทคโนโลยี |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Orchestration | LangGraph (`StateGraph`) |
| LLM gateway | `MultiplexedLLMClient` — vLLM หรือ OpenRouter (OpenAI-compatible), main+fallback, เลือก provider ได้ runtime |
| HTTP client | httpx (async) |
| Agency discovery | MCP (`fastmcp` client) |
| Session history | Redis (ถ้าตั้ง `REDIS_URL`) |
| LLM provider config + cost log | Postgres (`llm_provider_config`, `llm_call_log`, ถ้าตั้ง `DATABASE_URL`) |
| Config | Pydantic Settings + `.env` |

## เอกสารที่เกี่ยวข้อง

- [02-architecture.md](02-architecture.md) — โครงสร้างภายใน, LangGraph flow, การตัดสินใจเชิงออกแบบ
- [03-api.md](03-api.md) — endpoint, request/response schema ทั้ง 5 เวอร์ชัน
- [04-agents.md](04-agents.md) — งานที่ใช้ LLM และ agency adapter
- [05-roadmap.md](05-roadmap.md) — สิ่งที่เสร็จแล้ว vs ยังไม่เสร็จ
- [06-bugs.md](06-bugs.md) — ปัญหาที่รู้อยู่
