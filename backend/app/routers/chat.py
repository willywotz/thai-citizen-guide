"""
AI Chat router — port of the Supabase `ai-chat` edge function.

Flow
----
1. Detect target agencies from Thai keyword matching
2. Fetch agency response_schema configs from DB
3. Query each agency sub-handler in parallel (async)
4. Build a schema-guide prompt section
5. Synthesise a unified answer using the configured LLM (Gemini via AI Gateway)
6. Return structured response: answer, references, agentSteps, agencies, confidence

Endpoint
--------
  POST  /chat
"""

import asyncio
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import settings
from app.models.agency import Agency
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.auth.dependencies import get_current_user_optional
from app.utils import generate_uuid

router = APIRouter(prefix="/chat", tags=["Chat"])

# # ---------------------------------------------------------------------------
# # Agency metadata
# # ---------------------------------------------------------------------------

# AGENCY_NAME_MAP: dict[str, str] = {
#     "fda": "สำนักงานคณะกรรมการอาหารและยา",
#     "revenue": "กรมสรรพากร",
#     "dopa": "กรมการปกครอง",
#     "land": "กรมที่ดิน",
# }

# AGENCY_DISPLAY_MAP: dict[str, str] = {
#     "fda": "สำนักงาน อย.",
#     "revenue": "กรมสรรพากร",
#     "dopa": "กรมการปกครอง",
#     "land": "กรมที่ดิน",
# }

# AGENCY_ICON_MAP: dict[str, str] = {
#     "fda": "🏥",
#     "revenue": "💰",
#     "dopa": "🏛️",
#     "land": "🗺️",
# }

# # ---------------------------------------------------------------------------
# # Keyword-based agency detection (matches Deno original)
# # ---------------------------------------------------------------------------

# def detect_agencies(query: str) -> list[str]:
#     q = query.lower()
#     matched: list[str] = []

#     if any(k in q for k in ["ยา", "อาหาร", "เครื่องสำอาง", "อย.", "พาราเซตามอล", "นำเข้า", "ผลิตภัณฑ์สุขภาพ"]):
#         matched.append("fda")
#     if any(k in q for k in ["ภาษี", "ลดหย่อน", "สรรพากร", "vat", "ยื่นแบบ", "เงินได้"]):
#         matched.append("revenue")
#     if any(k in q for k in ["บัตรประชาชน", "ทะเบียนราษฎร์", "ทะเบียนบ้าน", "ปกครอง", "เปลี่ยนชื่อ", "แจ้งเกิด"]):
#         matched.append("dopa")
#     if any(k in q for k in ["ที่ดิน", "โฉนด", "ราคาประเมิน", "จดทะเบียน", "รังวัด", "โอนที่ดิน"]):
#         matched.append("land")

#     if not matched:
#         matched.append("fda")   # default fallback
#     return matched


# # ---------------------------------------------------------------------------
# # Agency sub-handlers (Python ports of the Deno agency-* edge functions)
# # ---------------------------------------------------------------------------

# _FDA_RESPONSES: dict[str, dict] = {
#     "ยา": {
#         "answer": (
#             "**ระบบตรวจสอบทะเบียนยา - สำนักงาน อย.**\n\n"
#             "ยาทุกชนิดที่จำหน่ายในประเทศไทยต้องขึ้นทะเบียนกับ อย. ตาม พ.ร.บ. ยา พ.ศ. 2510\n\n"
#             "**ประเภทยา:**\n"
#             "- ยาสามัญประจำบ้าน — ซื้อได้ทั่วไป\n"
#             "- ยาอันตราย — ต้องซื้อจากร้านขายยาที่มีเภสัชกร\n"
#             "- ยาควบคุมพิเศษ — ต้องมีใบสั่งแพทย์\n\n"
#             "**การตรวจสอบ:** สามารถตรวจสอบเลขทะเบียนยาได้ที่เว็บไซต์ อย. หรือแอป \"อย. Smart Application\""
#         ),
#         "references": [
#             {"title": "ระบบตรวจสอบทะเบียนยา", "url": "https://www.fda.moph.go.th/sites/drug"},
#             {"title": "พ.ร.บ. ยา พ.ศ. 2510", "url": "https://www.fda.moph.go.th/sites/drug/law"},
#         ],
#     },
#     "อาหาร": {
#         "answer": (
#             "**ระบบตรวจสอบทะเบียนอาหาร - สำนักงาน อย.**\n\n"
#             "ผลิตภัณฑ์อาหารที่จำหน่ายในประเทศไทยต้องได้รับอนุญาตจาก อย.\n\n"
#             "**เครื่องหมาย อย.:**\n"
#             "- เลข อย. 13 หลัก แสดงว่าผ่านการตรวจสอบ\n"
#             "- ตรวจสอบได้ที่เว็บไซต์ อย.\n\n"
#             "**ประเภทอาหาร:**\n"
#             "- อาหารควบคุมเฉพาะ\n- อาหารที่กำหนดคุณภาพ\n- อาหารที่ต้องมีฉลาก\n- อาหารทั่วไป"
#         ),
#         "references": [{"title": "ตรวจสอบเลข อย.", "url": "https://www.fda.moph.go.th/sites/food"}],
#     },
#     "เครื่องสำอาง": {
#         "answer": (
#             "**ระบบจดแจ้งเครื่องสำอาง - สำนักงาน อย.**\n\n"
#             "เครื่องสำอางทุกชนิดต้องจดแจ้งกับ อย. ก่อนจำหน่าย\n\n"
#             "**ขั้นตอน:**\n1. ยื่นจดแจ้งผ่านระบบ e-Submission\n"
#             "2. ตรวจสอบส่วนประกอบตามประกาศกระทรวง\n3. ได้รับเลขจดแจ้ง 10 หลัก\n\n"
#             "**สารต้องห้าม:** สารปรอท, ไฮโดรควิโนน, สเตียรอยด์"
#         ),
#         "references": [{"title": "ระบบจดแจ้งเครื่องสำอาง", "url": "https://www.fda.moph.go.th/sites/cosmetic"}],
#     },
# }

# _REVENUE_RESPONSES: dict[str, dict] = {
#     "ภาษี": {
#         "answer": (
#             "**ข้อมูลภาษีเงินได้บุคคลธรรมดา - กรมสรรพากร**\n\n"
#             "ภาษีเงินได้บุคคลธรรมดาคำนวณจากเงินได้สุทธิ หลังหักค่าใช้จ่ายและค่าลดหย่อนต่างๆ\n\n"
#             "**อัตราภาษี:**\n"
#             "- 0–150,000 บาท: ยกเว้น\n- 150,001–300,000 บาท: 5%\n"
#             "- 300,001–500,000 บาท: 10%\n- 500,001–750,000 บาท: 15%\n"
#             "- 750,001–1,000,000 บาท: 20%\n- 1,000,001–2,000,000 บาท: 25%\n"
#             "- 2,000,001–5,000,000 บาท: 30%\n- มากกว่า 5,000,000 บาท: 35%\n\n"
#             "**การยื่นแบบ:** ยื่น ภ.ง.ด.90/91 ภายใน 31 มีนาคมของปีถัดไป"
#         ),
#         "references": [
#             {"title": "คำนวณภาษีเงินได้", "url": "https://www.rd.go.th/publish/29554.0.html"},
#             {"title": "ยื่นแบบออนไลน์", "url": "https://efiling.rd.go.th"},
#         ],
#     },
#     "vat": {
#         "answer": (
#             "**ภาษีมูลค่าเพิ่ม (VAT) - กรมสรรพากร**\n\n"
#             "VAT อัตราปัจจุบัน 7% (รวมภาษีท้องถิ่น)\n\n"
#             "**ผู้มีหน้าที่เสียภาษี:** ผู้ประกอบการที่มีรายได้เกิน 1.8 ล้านบาทต่อปี\n\n"
#             "**การจดทะเบียน:** ยื่นจดทะเบียนภาษีมูลค่าเพิ่มที่สรรพากรพื้นที่ หรือผ่านระบบออนไลน์"
#         ),
#         "references": [{"title": "ข้อมูล VAT", "url": "https://www.rd.go.th/publish/6043.0.html"}],
#     },
# }

# _DOPA_RESPONSES: dict[str, dict] = {
#     "บัตรประชาชน": {
#         "answer": (
#             "**บัตรประจำตัวประชาชน - กรมการปกครอง**\n\n"
#             "บัตรประจำตัวประชาชนมีอายุ 8 ปี (สำหรับผู้มีอายุ 7–70 ปี)\n\n"
#             "**การทำบัตรใหม่:**\n1. ยื่นคำขอที่สำนักงานทะเบียนท้องถิ่น\n"
#             "2. เตรียมเอกสาร: สูติบัตร/ทะเบียนบ้าน\n"
#             "3. ถ่ายรูปและสแกนลายนิ้วมือ\n4. รับบัตรภายใน 3 วันทำการ\n\n"
#             "**ค่าธรรมเนียม:** 100 บาท (กรณีหมดอายุ ไม่เสียค่าธรรมเนียม)"
#         ),
#         "references": [
#             {"title": "บริการออกบัตรประชาชน", "url": "https://www.dopa.go.th/service/id_card"},
#         ],
#     },
#     "ทะเบียนบ้าน": {
#         "answer": (
#             "**ทะเบียนบ้าน - กรมการปกครอง**\n\n"
#             "**การแจ้งย้ายที่อยู่:**\n1. แจ้งย้ายออกที่เดิม\n2. แจ้งย้ายเข้าที่ใหม่\n"
#             "3. เจ้าบ้านเซ็นรับรอง\n4. ใช้เวลา 1 วันทำการ\n\n"
#             "**เอกสารที่ต้องใช้:** บัตรประชาชน + ทะเบียนบ้านเดิม"
#         ),
#         "references": [{"title": "ทะเบียนบ้าน", "url": "https://www.dopa.go.th/service/household"}],
#     },
# }

# _LAND_RESPONSES: dict[str, dict] = {
#     "โฉนด": {
#         "answer": (
#             "**โฉนดที่ดิน - กรมที่ดิน**\n\n"
#             "โฉนดที่ดิน (น.ส.4) เป็นเอกสารสิทธิสูงสุดในการถือครองที่ดิน\n\n"
#             "**ประเภทเอกสารสิทธิ์:**\n"
#             "- โฉนดที่ดิน (น.ส.4 จ.) — สิทธิสมบูรณ์\n"
#             "- น.ส.3 ก — สิทธิครอบครอง มีรูปถ่ายทางอากาศ\n"
#             "- ส.ป.ก. 4-01 — ที่ดินเพื่อการเกษตร\n\n"
#             "**การโอนกรรมสิทธิ์:** ทำที่สำนักงานที่ดินจังหวัด ค่าธรรมเนียม 2% ของราคาประเมิน"
#         ),
#         "references": [
#             {"title": "ตรวจสอบที่ดิน", "url": "https://www.dol.go.th/"},
#             {"title": "ราคาประเมินที่ดิน", "url": "https://property.treasury.go.th/"},
#         ],
#     },
#     "ราคาประเมิน": {
#         "answer": (
#             "**ราคาประเมินที่ดิน - กรมที่ดิน**\n\n"
#             "ราคาประเมินที่ดินกำหนดโดยกรมธนารักษ์ ใช้เป็นฐานในการคำนวณค่าธรรมเนียมการโอน\n\n"
#             "**การตรวจสอบ:** ตรวจสอบราคาประเมินได้ที่เว็บไซต์กรมธนารักษ์ หรือสำนักงานที่ดิน\n\n"
#             "**ค่าธรรมเนียมการโอน:**\n- ค่าธรรมเนียม: 2%\n- ภาษีธุรกิจเฉพาะ: 3.3% (ถือครองน้อยกว่า 5 ปี)\n- อากรแสตมป์: 0.5% (กรณีไม่เสียภาษีธุรกิจเฉพาะ)"
#         ),
#         "references": [{"title": "ราคาประเมินที่ดิน", "url": "https://property.treasury.go.th/"}],
#     },
# }


# def _query_fda(query: str) -> dict:
#     q = query.lower()
#     if any(k in q for k in ["ยา", "พาราเซตามอล", "drug"]):
#         r = _FDA_RESPONSES["ยา"]
#     elif any(k in q for k in ["อาหาร", "food"]):
#         r = _FDA_RESPONSES["อาหาร"]
#     elif any(k in q for k in ["เครื่องสำอาง", "cosmetic"]):
#         r = _FDA_RESPONSES["เครื่องสำอาง"]
#     else:
#         r = _FDA_RESPONSES["ยา"]
#     return {
#         "success": True, "agency": "fda",
#         "agencyName": AGENCY_NAME_MAP["fda"],
#         "data": {"answer": r["answer"], "references": r["references"], "confidence": 0.95},
#     }


# def _query_revenue(query: str) -> dict:
#     q = query.lower()
#     r = _REVENUE_RESPONSES["vat"] if "vat" in q else _REVENUE_RESPONSES["ภาษี"]
#     return {
#         "success": True, "agency": "revenue",
#         "agencyName": AGENCY_NAME_MAP["revenue"],
#         "data": {"answer": r["answer"], "references": r["references"], "confidence": 0.93},
#     }


# def _query_dopa(query: str) -> dict:
#     q = query.lower()
#     r = _DOPA_RESPONSES["ทะเบียนบ้าน"] if "ทะเบียนบ้าน" in q else _DOPA_RESPONSES["บัตรประชาชน"]
#     return {
#         "success": True, "agency": "dopa",
#         "agencyName": AGENCY_NAME_MAP["dopa"],
#         "data": {"answer": r["answer"], "references": r["references"], "confidence": 0.91},
#     }


# def _query_land(query: str) -> dict:
#     q = query.lower()
#     r = _LAND_RESPONSES["ราคาประเมิน"] if "ราคาประเมิน" in q else _LAND_RESPONSES["โฉนด"]
#     return {
#         "success": True, "agency": "land",
#         "agencyName": AGENCY_NAME_MAP["land"],
#         "data": {"answer": r["answer"], "references": r["references"], "confidence": 0.90},
#     }


# _AGENCY_HANDLERS = {
#     "fda": _query_fda,
#     "revenue": _query_revenue,
#     "dopa": _query_dopa,
#     "land": _query_land,
# }


# async def _call_agency(agency_id: str, query: str) -> dict | None:
#     """Call the internal agency handler (async-safe wrapper)."""
#     handler = _AGENCY_HANDLERS.get(agency_id)
#     if not handler:
#         return None
#     return handler(query)


# # ---------------------------------------------------------------------------
# # Schema guide builder (matches Deno original)
# # ---------------------------------------------------------------------------

# def _build_schema_guide(agency_configs: list[Any], target_agencies: list[str]) -> str:
#     sections: list[str] = []
#     for agency_id in target_agencies:
#         config = None
#         for c in agency_configs:
#             sn = (c.get("short_name") or "").replace(".", "").lower()
#             name = c.get("name", "")
#             if (
#                 (agency_id == "fda" and ("อย" in sn or "อาหาร" in name)) or
#                 (agency_id == "revenue" and ("สรรพากร" in sn or "สรรพากร" in name)) or
#                 (agency_id == "dopa" and ("ปกครอง" in sn or "ปกครอง" in name)) or
#                 (agency_id == "land" and ("ที่ดิน" in sn or "ที่ดิน" in name))
#             ):
#                 config = c
#                 break

#         schema = config.get("response_schema") if config else None
#         if not schema:
#             continue

#         fields_text = "\n".join(
#             f"  - **{f['field']}** ({f['type']}): {f['description']}"
#             + (f" — ตัวอย่าง: {f['example']}" if f.get("example") else "")
#             for f in schema
#         )
#         sections.append(
#             f"#### {config['name']} ({config['short_name']})\n"
#             f"Response fields ที่สำคัญ:\n{fields_text}"
#         )

#     if not sections:
#         return ""
#     return (
#         "\n\n## Schema Reference สำหรับ Parse ข้อมูล\n"
#         "ใช้ข้อมูล schema ด้านล่างเพื่อระบุและจัดรูปแบบข้อมูลในคำตอบให้ถูกต้อง:\n\n"
#         + "\n\n".join(sections)
#     )


# # ---------------------------------------------------------------------------
# # Chat endpoint
# # ---------------------------------------------------------------------------

# @router.post("/asdasd", summary="Send a query and get a synthesised AI response")
# async def chat(body: ChatRequest, user: User | None = Depends(get_current_user_optional)) -> ChatResponse:
#     start = time.time()
#     query = body.query.strip()

#     if not query:
#         return {"success": False, "error": "Missing query"}

#     # 1. Detect target agencies
#     target_agencies = detect_agencies(query)

#     # 2. Fetch agency configs from DB (for schema guide)
#     agency_configs: list[dict] = []
#     try:
#         agencies = await Agency.filter(status="active").values(
#             "id", "short_name", "name", "logo", "response_schema", "api_endpoints", "connection_type"
#         )
#         agency_configs = list(agencies)
#     except Exception as exc:
#         print(f"[chat] Failed to fetch agency configs: {exc}")

#     # 3. Build agent steps
#     agency_display_names = [AGENCY_DISPLAY_MAP.get(a, a) for a in target_agencies]
#     agent_steps = [
#         {"icon": "🔍", "label": "กำลังวิเคราะห์คำถาม...", "status": "done"},
#         {
#             "icon": "📋",
#             "label": f"วางแผนการสืบค้น → เลือกหน่วยงาน: {', '.join(agency_display_names)}",
#             "status": "done",
#         },
#     ]

#     # 4. Call agencies in parallel
#     for a in target_agencies:
#         agent_steps.append({
#             "icon": "🔗",
#             "label": f"กำลังสืบค้นจาก {AGENCY_DISPLAY_MAP.get(a, a)} ...",
#             "status": "done",
#         })

#     results = await asyncio.gather(*[_call_agency(a, query) for a in target_agencies])
#     valid_results = [r for r in results if r is not None]

#     agent_steps.append({"icon": "✅", "label": "รวบรวมและประเมินผลลัพธ์", "status": "done"})

#     # 5. LLM synthesis
#     schema_guide = _build_schema_guide(agency_configs, target_agencies)
#     combined_answer = "\n\n---\n\n".join(r["data"]["answer"] for r in valid_results)

#     llm_api_key = settings.PARSE_SPEC_API_KEY
#     if llm_api_key and valid_results:
#         agent_steps.append({
#             "icon": "🤖",
#             "label": "AI กำลังสังเคราะห์คำตอบ (พร้อม Schema Guide)...",
#             "status": "done",
#         })

#         agency_context = "\n\n".join(
#             f"### ข้อมูลจาก {r['agencyName']}\n{r['data']['answer']}" for r in valid_results
#         )

#         system_prompt = (
#             "คุณคือ AI ผู้ช่วยภาครัฐไทย ทำหน้าที่สังเคราะห์ข้อมูลจากหลายหน่วยงานราชการให้เป็นคำตอบที่ชัดเจน ถูกต้อง และเข้าใจง่ายสำหรับประชาชน\n\n"
#             "กฎ:\n"
#             "- ตอบเป็นภาษาไทยเสมอ\n"
#             "- ใช้ Markdown formatting (หัวข้อ, bullet points, ตัวหนา) ให้อ่านง่าย\n"
#             "- อ้างอิงชื่อหน่วยงานที่เป็นแหล่งข้อมูลในคำตอบ\n"
#             "- หากข้อมูลจากหลายหน่วยงานเกี่ยวข้องกัน ให้เชื่อมโยงและสรุปให้เป็นคำตอบเดียวที่สอดคล้องกัน\n"
#             "- ห้ามเพิ่มข้อมูลที่ไม่มีในแหล่งข้อมูลที่ให้มา\n"
#             "- จบคำตอบด้วยข้อแนะนำเพิ่มเติมหากเหมาะสม"
#             + (
#                 "\n- เมื่อมี Schema Reference ให้ใช้เป็นแนวทางในการระบุและจัดรูปแบบข้อมูลสำคัญ"
#                 + schema_guide
#                 if schema_guide else ""
#             )
#         )
#         user_prompt = (
#             f'คำถามจากประชาชน: "{query}"\n\n'
#             f"ข้อมูลที่สืบค้นได้จากหน่วยงานราชการ:\n\n{agency_context}\n\n"
#             "กรุณาสังเคราะห์ข้อมูลข้างต้นเป็นคำตอบที่ครบถ้วนและเข้าใจง่ายสำหรับประชาชน"
#         )

#         try:
#             async with httpx.AsyncClient(timeout=30.0) as client:
#                 resp = await client.post(
#                     settings.PARSE_SPEC_URL,
#                     headers={
#                         "apikey": f"{llm_api_key}",
#                         "Content-Type": "application/json",
#                     },
#                     json={
#                         "model": settings.PARSE_SPEC_LLM_MODEL,
#                         "messages": [
#                             {"role": "system", "content": system_prompt},
#                             {"role": "user", "content": user_prompt},
#                         ],
#                     },
#                 )
#             if resp.status_code == 200:
#                 ai_data = resp.json()
#                 combined_answer = (
#                     ai_data.get("choices", [{}])[0].get("message", {}).get("content")
#                     or combined_answer
#                 )
#         except Exception as exc:
#             print(f"[chat] LLM error: {exc}")

#     agent_steps.append({"icon": "📝", "label": "สังเคราะห์คำตอบเสร็จสิ้น", "status": "done"})

#     all_references = [
#         {"agency": r["agencyName"], **ref}
#         for r in valid_results
#         for ref in r["data"].get("references", [])
#     ]

#     avg_confidence = (
#         sum(r["data"].get("confidence", 0) for r in valid_results) / len(valid_results)
#         if valid_results else 0.0
#     )

#     response_time = int((time.time() - start) * 1000)

#     if not body.conversation_id:
#         conv = await Conversation.create(
#             title=query[:50],
#             preview=query[:100],
#             agencies=[{"id": a, "name": AGENCY_DISPLAY_MAP.get(a, a), "icon": AGENCY_ICON_MAP.get(a, "")} for a in target_agencies],
#             status='success',
#             message_count=len(combined_answer),
#             response_time=response_time,
#             user_id=user.id if user else None,
#         )
#     else:
#         conv = await Conversation.get(id=body.conversation_id)
#         conv.message_count += len(combined_answer)
#         await conv.save()

#     await Message.bulk_create([
#         Message(
#             conversation_id=conv.id,
#             role='user',
#             content=query,
#             agent_steps=[],
#             sources=[{"agency": r["agencyName"], **ref} for r in valid_results for ref in r["data"].get("references", [])],
#         ),
#         Message(
#             conversation_id=conv.id,
#             role='assistant',
#             content=combined_answer,
#             agent_steps=agent_steps,
#             sources=[{"agency": r["agencyName"], **ref} for r in valid_results for ref in r["data"].get("references", [])],
#             response_time=response_time,
#         ),
#     ], ignore_conflicts=True)

#     return {
#         "success": True,
#         "data": {
#             "answer": combined_answer,
#             "references": all_references,
#             "agentSteps": agent_steps,
#             "agencies": [
#                 {"id": a, "name": AGENCY_DISPLAY_MAP.get(a, a), "icon": AGENCY_ICON_MAP.get(a, "")}
#                 for a in target_agencies
#             ],
#             "confidence": avg_confidence,
#         },
#         "conversation_id": conv.id,
#         "responseTime": response_time,
#     }

"""
Multi-Agent Router with LangGraph
==================================
Dynamic agency routing — ดึง agency list จาก MCP tool แล้ว route query
ไปยัง agency ที่เกี่ยวข้องผ่าน A2A / API / MCP adapters
"""

import dotenv
dotenv.load_dotenv()

import os
import asyncio
import re
import json
import uuid
import operator
from typing import Annotated, Any
from dataclasses import dataclass, field

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END


# ─── State ────────────────────────────────────────────────────────────────────

@dataclass
class AgentState:
    query: str = ""
    conversation_id: str = ""

    agencies: list[dict] = field(default_factory=list)
    routes: list[dict] = field(default_factory=list)
    results: Annotated[list[dict], operator.add] = field(default_factory=list)
    final_answer: str = ""


# ─── Config ───────────────────────────────────────────────────────────────────

# LLM = ChatOpenAI(
#     model="/model",
#     temperature=0,

#     openai_api_key="sk-placeholder",
#     openai_api_base=os.getenv("PARSE_SPEC_URL", ""),
#     default_headers={
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
#         "apikey": os.getenv("PARSE_SPEC_API_KEY", ""),
#     },
# )

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

async def call_llm(messages: list[dict], conversation_id: str | None = None) -> str:

    request_messages = [
        SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages
    ]

    llm_response = await llm.ainvoke(request_messages)
    print(f"LLM response: {llm_response.content}")

    return {"content": llm_response.content}

    # llm_api_key = os.getenv("PARSE_SPEC_API_KEY", "")
    # if not llm_api_key:
    #     raise ValueError("Missing LLM API key")

    # print(f"Calling LLM with messages: {messages}")

    # async with httpx.AsyncClient(timeout=60.0) as client:
    #     resp = await client.post(
    #         os.getenv("PARSE_SPEC_URL", ""),
    #         headers={
    #             "apikey": f"{llm_api_key}",
    #             "Content-Type": "application/json",
    #         },
    #         json={
    #             "model": os.getenv("PARSE_SPEC_LLM_MODEL", "gpt-3.5-turbo"),
    #             "messages": messages,
    #         },
    #     )
    # if resp.status_code == 200:
    #     resp_data = resp.json()
    #     print(f"LLM response: {resp_data}")
    #     return resp_data.get("choices", [{}])[0].get("message", {})
    # else:
    #     raise ValueError(f"LLM API error: {resp.status_code} {resp.text}")


# ─── Prompt Builder ───────────────────────────────────────────────────────────

def build_router_prompt(agencies: list[dict]) -> str:
    """สร้าง system prompt พร้อม available sources จาก agency list"""

    source_lines = []
    for ag in agencies:
        scope = ", ".join(ag.get("data_scope", []))
        source_lines.append(
            f'- {ag["name"]} (id: {ag["id"]}, type: {ag["connection_type"]}), endpoint_url: {ag.get("endpoint_url", "")}: '
            f'{ag["description"]} — ขอบเขตข้อมูล: {scope}'
        )

    sources_block = "\n".join(source_lines)

    return f"""\
คุณคือ Router Agent ที่วิเคราะห์คำถามผู้ใช้แล้วเลือกหน่วยงานที่เกี่ยวข้อง
สำหรับแต่ละหน่วยงาน ให้สร้าง sub-question ที่เหมาะกับขอบเขตข้อมูลของหน่วยงานนั้น

Available sources:
{sources_block}

ตอบเป็น JSON เท่านั้น ห้ามมี text อื่น:
{{
  "routes": [
    {{
      "agency_id": "<uuid>",
      "agency_name": "<ชื่อหน่วยงาน>",
      "connection_type": "<A2A|API|MCP>",
      "endpoint_url": "<endpoint_url>",
      "sub_question": "<คำถามที่ปรับให้เหมาะกับหน่วยงานนี้>"
    }}
  ]
}}

กฎ:
- เลือกเฉพาะหน่วยงานที่เกี่ยวข้องจริงๆ อย่าเลือกทุกอัน
- sub_question ต้องเจาะจงกับ data_scope ของหน่วยงานนั้น
- ถ้าไม่มีหน่วยงานไหนเกี่ยวข้อง ให้ตอบ {{"routes": []}}"""


# ─── Nodes ────────────────────────────────────────────────────────────────────

async def load_agencies(state: AgentState) -> dict:
    """Node 1: ดึง agency list จาก MCP tool / API"""

    # state log
    print(f"[Node 1] Loading agencies for query: {state.query}")

    # === Production: call MCP tool หรือ REST API ===
    # async with httpx.AsyncClient() as client:
    #     resp = await client.get(AGENCY_LIST_URL)
    #     data = resp.json()
    #     return {"agencies": data["data"]}

    agencies = await Agency.filter(status="active").all().values()
    return {"agencies": agencies}


async def route_query(state: AgentState) -> dict:
    """Node 2: LLM วิเคราะห์ query แล้วเลือก agencies + สร้าง sub-questions"""

    print(f"[Node 2] Routing query: {state.query} with agencies: {state.agencies}")

    system_prompt = build_router_prompt(state.agencies)

    response = await call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": state.query},
    ], conversation_id=state.conversation_id)

    # parse JSON จาก LLM response
    text = response.get("content", "").strip()

    # strip markdown fences ถ้ามี
    if '<think>' in text:
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]

    parsed = json.loads(text)
    routes = parsed.get("routes", [])

    # enrich route ด้วย endpoint info
    agency_map = {ag["id"]: ag for ag in state.agencies}
    for route in routes:
        ag = agency_map.get(route["agency_id"], {})
        route["endpoint_url"] = ag.get("endpoint_url", "")
        route["expected_payload"] = ag.get("expected_payload", {})
        route["conversation_id"] = state.conversation_id

    return {"routes": routes}


async def dispatch_to_agencies(state: AgentState) -> dict:
    """Node 3: ส่ง sub-question ไปแต่ละ agency ตาม connection_type"""

    print(f"[Node 3] Dispatching to agencies with routes: {state.routes}")

    async def call_agency(route: dict) -> dict:
        """Dispatch ตาม connection_type"""
        conn = route["connection_type"]
        sub_q = route["sub_question"]
        name = route["agency_name"]

        try:
            # ─── A2A Protocol ───
            if conn == "A2A":
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        route["endpoint_url"],
                        json={
                            # "jsonrpc": "2.0",
                            # "method": "message/send",
                            # "params": {"message": {"text": sub_q}},
                            "query": sub_q,
                        },
                        headers={"Content-Type": "application/json"},
                    )
                    return {"agency": name, "response": resp.json(), "status": "ok"}
                # return {"agency": name, "response": f"[A2A mock] ตอบจาก {name}: {sub_q}", "status": "ok"}

            # ─── REST API ───
            elif conn == "API":
                payload = route.get("expected_payload") or {}
                # แทนที่ placeholder
                if "query" in payload:
                    payload = {**payload, "query": sub_q}
                # async with httpx.AsyncClient(timeout=30) as client:
                #     resp = await client.post(route["endpoint_url"], json=payload)
                #     return {"agency": name, "response": resp.json(), "status": "ok"}
                return {"agency": name, "response": f"[API mock] ตอบจาก {name}: {sub_q}", "status": "ok"}

            # ─── MCP Protocol ───
            elif conn == "MCP":
                # MCP call via SDK
                # result = await mcp_client.call_tool(route["endpoint_url"], {"query": sub_q})
                # return {"agency": name, "response": result, "status": "ok"}
                return {"agency": name, "response": f"[MCP mock] ตอบจาก {name}: {sub_q}", "status": "ok"}

            else:
                return {"agency": name, "response": f"Unknown connection_type: {conn}", "status": "error"}

        except Exception as e:
            return {"agency": name, "response": str(e), "status": "error"}

    # fire all agencies concurrently
    tasks = [call_agency(route) for route in state.routes]
    results = await asyncio.gather(*tasks)

    return {"results": list(results)}


async def synthesize(state: AgentState) -> dict:
    """Node 4: รวมผลลัพธ์จากทุก agency เป็นคำตอบเดียว"""

    print(f"[Node 4] Synthesizing results: {state.results}")

    if not state.results:
        return {"final_answer": "ไม่พบหน่วยงานที่เกี่ยวข้องกับคำถามของคุณ"}

    results_text = "\n\n".join(
        f"### {r['agency']}\n{r['response']}" for r in state.results
    )

    response = await call_llm([
        {"role": "system", "content": """\
คุณคือ Synthesizer Agent สรุปข้อมูลจากหลายหน่วยงานราชการเป็นคำตอบเดียวที่ครบถ้วน
- ตอบเป็นภาษาไทย
- อ้างอิงว่าข้อมูลมาจากหน่วยงานไหน
- ถ้ามี error ให้แจ้งผู้ใช้ว่าหน่วยงานไหนไม่สามารถตอบได้"""},
        {"role": "user", "content": f"คำถามเดิม: {state.query}\n\nผลลัพธ์จากหน่วยงาน:\n{results_text}"},
    ], conversation_id=state.conversation_id)

    return {"final_answer": response.get("content", "").strip()}


# ─── Conditional Edge ─────────────────────────────────────────────────────────

def should_dispatch(state: AgentState) -> str:
    """ถ้าไม่มี route เลย ข้ามไป synthesize เลย"""

    print(f"[Conditional] Checking if should dispatch with routes: {state.routes}")

    return "dispatch" if state.routes else "synthesize"


# ─── Graph ────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # nodes
    graph.add_node("load_agencies", load_agencies)
    graph.add_node("route_query", route_query)
    graph.add_node("dispatch", dispatch_to_agencies)
    graph.add_node("synthesize", synthesize)

    # edges
    graph.add_edge(START, "load_agencies")
    graph.add_edge("load_agencies", "route_query")
    graph.add_conditional_edges("route_query", should_dispatch, {
        "dispatch": "dispatch",
        "synthesize": "synthesize",
    })
    graph.add_edge("dispatch", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    app = build_graph()

    queries = [
        # "อยากเปลี่ยนชื่อในบัตรประชาชน ต้องเสียภาษีอะไรเพิ่มไหม",
        # "ยาพาราเซตามอลตัวไหนผ่าน อย. บ้าง",
        # "อยากซื้อที่ดิน ต้องตรวจสอบโฉนดยังไง แล้วเสียภาษีอะไรบ้าง",
        "ขั้นตอนการทำบัตรประชาชนใหม่",
    ]

    for q in queries:
        print(f"\n{'='*70}")
        print(f"Q: {q}")
        print(f"{'='*70}")

        result = await app.ainvoke({"query": q})

        print(f"\n📌 Routes:")
        for r in result["routes"]:
            print(f"  → {r['agency_name']} ({r['connection_type']})")
            print(f"    sub-question: {r['sub_question']}")

        print(f"\n📋 Results:")
        for r in result["results"]:
            print(f"  [{r['status']}] {r['agency']}: {r['response']}")

        print(f"\n✅ Final Answer:\n{result['final_answer']}")


if __name__ == "__main__":
    asyncio.run(main())

@router.post("", summary="Send a query and get a synthesised AI response")
async def chat(body: ChatRequest, user: User | None = Depends(get_current_user_optional)) -> ChatResponse:
    start = time.time()
    query = body.query.strip()

    if not query:
        return {"success": False, "error": "Missing query"}

    conversation_id = body.conversation_id or str(generate_uuid())
    
    app = build_graph()
    
    result = await app.ainvoke({"query": query, "conversation_id": conversation_id})

    response_time = int((time.time() - start) * 1000)
    
    answer = result.get("final_answer", "")

    if not body.conversation_id:
        conv = await Conversation.create(
            id=conversation_id,
            title=query[:50],
            preview=query[:100],
            agencies=[],
            status='success',
            message_count=len(answer),
            response_time=response_time,
            user_id=user.id if user else None,
        )
    else:
        conv = await Conversation.get(id=conversation_id)
        conv.message_count += len(answer)
        await conv.save()

    await Message.bulk_create([
        Message(
            conversation_id=conversation_id,
            role='user',
            content=query,
            agent_steps=[],
            sources=[],
        ),
        Message(
            conversation_id=conversation_id,
            role='assistant',
            content=answer,
            agent_steps=[],
            sources=[],
            response_time=response_time,
        ),
    ], ignore_conflicts=True)

    return {
        "success": True,
        "data": {
            "answer": result['final_answer'],
            "references": [],
            "agentSteps": [],
            "agencies": [],
            "confidence": 0.0,
        },
        "conversation_id": conversation_id,
        "responseTime": response_time,
    }