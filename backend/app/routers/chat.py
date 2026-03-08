import asyncio
import random
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..config import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])

AGENCY_NAME_MAP = {
    "fda": "สำนักงาน อย.",
    "revenue": "กรมสรรพากร",
    "dopa": "กรมการปกครอง",
    "land": "กรมที่ดิน",
}

AGENCY_ICON_MAP = {
    "fda": "🏥",
    "revenue": "💰",
    "dopa": "🏛️",
    "land": "🗺️",
}

# Static knowledge bases (mirrors original edge functions)
FDA_RESPONSES = {
    "ยา": {
        "answer": "**ระบบตรวจสอบทะเบียนยา - สำนักงาน อย.**\n\nยาทุกชนิดที่จำหน่ายในประเทศไทยต้องขึ้นทะเบียนกับ อย. ตาม พ.ร.บ. ยา พ.ศ. 2510\n\n**ประเภทยา:**\n- ยาสามัญประจำบ้าน — ซื้อได้ทั่วไป\n- ยาอันตราย — ต้องซื้อจากร้านขายยาที่มีเภสัชกร\n- ยาควบคุมพิเศษ — ต้องมีใบสั่งแพทย์\n\n**การตรวจสอบ:** สามารถตรวจสอบเลขทะเบียนยาได้ที่เว็บไซต์ อย. หรือแอป \"อย. Smart Application\"",
        "references": [
            {"title": "ระบบตรวจสอบทะเบียนยา", "url": "https://www.fda.moph.go.th/sites/drug"},
            {"title": "พ.ร.บ. ยา พ.ศ. 2510", "url": "https://www.fda.moph.go.th/sites/drug/law"},
        ],
    },
    "อาหาร": {
        "answer": "**ระบบตรวจสอบทะเบียนอาหาร - สำนักงาน อย.**\n\nผลิตภัณฑ์อาหารที่จำหน่ายในประเทศไทยต้องได้รับอนุญาตจาก อย.\n\n**เครื่องหมาย อย.:**\n- เลข อย. 13 หลัก แสดงว่าผ่านการตรวจสอบ\n- ตรวจสอบได้ที่เว็บไซต์ อย.\n\n**ประเภทอาหาร:**\n- อาหารควบคุมเฉพาะ\n- อาหารที่กำหนดคุณภาพ\n- อาหารที่ต้องมีฉลาก\n- อาหารทั่วไป",
        "references": [{"title": "ตรวจสอบเลข อย.", "url": "https://www.fda.moph.go.th/sites/food"}],
    },
    "เครื่องสำอาง": {
        "answer": "**ระบบจดแจ้งเครื่องสำอาง - สำนักงาน อย.**\n\nเครื่องสำอางทุกชนิดต้องจดแจ้งกับ อย. ก่อนจำหน่าย\n\n**ขั้นตอน:**\n1. ยื่นจดแจ้งผ่านระบบ e-Submission\n2. ตรวจสอบส่วนประกอบตามประกาศกระทรวง\n3. ได้รับเลขจดแจ้ง 10 หลัก\n\n**สารต้องห้าม:** สารปรอท, ไฮโดรควิโนน, สเตียรอยด์",
        "references": [{"title": "ระบบจดแจ้งเครื่องสำอาง", "url": "https://www.fda.moph.go.th/sites/cosmetic"}],
    },
}

REVENUE_RESPONSES = {
    "ภาษี": {
        "answer": "**ระบบภาษีเงินได้บุคคลธรรมดา - กรมสรรพากร**\n\nบุคคลธรรมดาที่มีเงินได้เกิน 120,000 บาทต่อปีต้องยื่นแบบ ภ.ง.ด.90/91\n\n**ช่องทางการยื่นแบบ:**\n- ออนไลน์: efiling.rd.go.th\n- สำนักงานสรรพากรพื้นที่ทุกแห่ง\n\n**กำหนดเวลา:**\n- ยื่นแบบปกติ: ภายใน 31 มีนาคม\n- ยื่นแบบออนไลน์: ภายใน 8 เมษายน",
        "references": [
            {"title": "ระบบยื่นแบบออนไลน์", "url": "https://efiling.rd.go.th"},
            {"title": "กรมสรรพากร", "url": "https://www.rd.go.th"},
        ],
    },
    "vat": {
        "answer": "**ภาษีมูลค่าเพิ่ม (VAT) - กรมสรรพากร**\n\nอัตราภาษี VAT ปัจจุบัน 7%\n\n**ผู้ประกอบการที่ต้องจดทะเบียน VAT:**\n- มีรายได้จากการขายสินค้า/บริการเกิน 1.8 ล้านบาทต่อปี\n\n**การยื่นแบบ:**\n- ยื่นแบบ ภ.พ.30 ทุกเดือนภายในวันที่ 15",
        "references": [{"title": "ข้อมูล VAT", "url": "https://www.rd.go.th/vat"}],
    },
}

DOPA_RESPONSES = {
    "บัตรประชาชน": {
        "answer": "**บัตรประจำตัวประชาชน - กรมการปกครอง**\n\n**เอกสารที่ต้องใช้:**\n- บัตรประจำตัวประชาชนเดิม (กรณีต่ออายุ)\n- ทะเบียนบ้านฉบับเจ้าบ้าน\n\n**สถานที่ทำบัตร:**\n- สำนักงานเขต/อำเภอทุกแห่ง\n- จุดบริการในห้างสรรพสินค้า (บางแห่ง)\n\n**ค่าธรรมเนียม:** 100 บาท\n**ระยะเวลา:** บัตรมีอายุ 8 ปี",
        "references": [{"title": "กรมการปกครอง", "url": "https://www.dopa.go.th"}],
    },
    "ทะเบียนบ้าน": {
        "answer": "**ทะเบียนบ้าน - กรมการปกครอง**\n\nทะเบียนบ้านเป็นเอกสารสำคัญที่แสดงที่อยู่อาศัยตามกฎหมาย\n\n**การแจ้งย้ายที่อยู่:**\n- แจ้งย้ายออกจากที่อยู่เดิม\n- แจ้งย้ายเข้าที่อยู่ใหม่ภายใน 15 วัน\n\n**เอกสารที่ต้องใช้:**\n- บัตรประชาชน\n- ทะเบียนบ้านเจ้าบ้าน (กรณีย้ายเข้า)",
        "references": [{"title": "บริการทะเบียนราษฎร", "url": "https://www.dopa.go.th/main/web_index"}],
    },
}

LAND_RESPONSES = {
    "ที่ดิน": {
        "answer": "**การจดทะเบียนสิทธิและนิติกรรม - กรมที่ดิน**\n\n**เอกสารสิทธิที่ดินประเภทต่างๆ:**\n- โฉนดที่ดิน (น.ส.4) — สิทธิสมบูรณ์ที่สุด\n- น.ส.3ก — สามารถออกโฉนดได้\n- ส.ป.ก. — ที่ดินเพื่อการเกษตร\n\n**การโอนกรรมสิทธิ์:**\n- ค่าธรรมเนียม 2% ของราคาประเมิน\n- ภาษีธุรกิจเฉพาะ 3.3% (กรณีขายภายใน 5 ปี)\n\n**ตรวจสอบราคาประเมิน:** ที่เว็บไซต์กรมที่ดิน",
        "references": [
            {"title": "กรมที่ดิน", "url": "https://www.dol.go.th"},
            {"title": "ตรวจสอบราคาประเมิน", "url": "https://dolwms.dol.go.th/tvd/"},
        ],
    },
    "โฉนด": {
        "answer": "**โฉนดที่ดิน - กรมที่ดิน**\n\nโฉนดที่ดินเป็นเอกสารสิทธิสูงสุดในการครอบครองที่ดิน\n\n**การออกโฉนดที่ดิน:**\n- ยื่นคำขอที่สำนักงานที่ดินจังหวัด/สาขา\n- รังวัดตรวจสอบแนวเขต\n- ระยะเวลาดำเนินการ 30-90 วัน\n\n**ค่าธรรมเนียม:** ขึ้นอยู่กับขนาดที่ดิน",
        "references": [{"title": "ระบบรังวัดออนไลน์", "url": "https://www.dol.go.th/survey"}],
    },
}


def detect_agencies(query: str) -> list[str]:
    q = query.lower()
    matched = []
    if any(k in q for k in ["ยา", "อาหาร", "เครื่องสำอาง", "อย.", "พาราเซตามอล", "นำเข้า", "ผลิตภัณฑ์สุขภาพ"]):
        matched.append("fda")
    if any(k in q for k in ["ภาษี", "ลดหย่อน", "สรรพากร", "vat", "ยื่นแบบ", "เงินได้"]):
        matched.append("revenue")
    if any(k in q for k in ["บัตรประชาชน", "ทะเบียนราษฎร์", "ทะเบียนบ้าน", "ปกครอง", "เปลี่ยนชื่อ", "แจ้งเกิด"]):
        matched.append("dopa")
    if any(k in q for k in ["ที่ดิน", "โฉนด", "ราคาประเมิน", "จดทะเบียน", "รังวัด", "โอนที่ดิน"]):
        matched.append("land")
    if not matched:
        matched.append("fda")
    return matched


def query_agency(agency_id: str, query: str) -> dict:
    q = query.lower()
    start = time.time()

    if agency_id == "fda":
        if any(k in q for k in ["ยา", "พาราเซตามอล", "drug"]):
            result = FDA_RESPONSES["ยา"]
        elif any(k in q for k in ["อาหาร", "food", "อย."]):
            result = FDA_RESPONSES["อาหาร"]
        elif any(k in q for k in ["เครื่องสำอาง", "cosmetic"]):
            result = FDA_RESPONSES["เครื่องสำอาง"]
        else:
            result = FDA_RESPONSES["ยา"]
    elif agency_id == "revenue":
        if "vat" in q:
            result = REVENUE_RESPONSES["vat"]
        else:
            result = REVENUE_RESPONSES["ภาษี"]
    elif agency_id == "dopa":
        if any(k in q for k in ["ทะเบียนบ้าน", "ย้าย"]):
            result = DOPA_RESPONSES["ทะเบียนบ้าน"]
        else:
            result = DOPA_RESPONSES["บัตรประชาชน"]
    elif agency_id == "land":
        if "โฉนด" in q:
            result = LAND_RESPONSES["โฉนด"]
        else:
            result = LAND_RESPONSES["ที่ดิน"]
    else:
        result = {"answer": "ไม่พบข้อมูล", "references": []}

    return {
        "success": True,
        "agency": agency_id,
        "agencyName": AGENCY_NAME_MAP[agency_id],
        "data": {
            "answer": result["answer"],
            "references": result["references"],
            "confidence": round(0.92 + random.random() * 0.07, 2),
        },
        "responseTime": int((time.time() - start) * 1000),
    }


class ChatRequest(BaseModel):
    query: str


@router.post("")
async def chat(body: ChatRequest):
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=400, detail="Missing query parameter")

    start = time.time()
    target_agencies = detect_agencies(body.query)

    agent_steps = [
        {"icon": "🔍", "label": "กำลังวิเคราะห์คำถาม...", "status": "done"},
        {
            "icon": "📋",
            "label": f"วางแผนการสืบค้น → เลือกหน่วยงาน: {', '.join(AGENCY_NAME_MAP[a] for a in target_agencies)}",
            "status": "done",
        },
    ]

    # Query agencies in parallel
    loop = asyncio.get_event_loop()
    results = await asyncio.gather(
        *[
            loop.run_in_executor(None, query_agency, agency_id, body.query)
            for agency_id in target_agencies
        ]
    )

    for agency_id in target_agencies:
        agent_steps.append({
            "icon": "🔗",
            "label": f"กำลังสืบค้นจาก {AGENCY_NAME_MAP[agency_id]} ...",
            "status": "done",
        })

    agent_steps.append({"icon": "✅", "label": "รวบรวมและประเมินผลลัพธ์", "status": "done"})

    # Synthesize with OpenAI if configured
    combined_answer: str
    if settings.openai_api_key and results:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

            agency_context = "\n\n".join(
                f"### ข้อมูลจาก {r['agencyName']}\n{r['data']['answer']}" for r in results
            )
            agent_steps.append({"icon": "🤖", "label": "AI กำลังสังเคราะห์คำตอบ...", "status": "done"})

            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "คุณคือ AI ผู้ช่วยภาครัฐไทย ทำหน้าที่สังเคราะห์ข้อมูลจากหลายหน่วยงานราชการให้เป็นคำตอบที่ชัดเจน ถูกต้อง และเข้าใจง่ายสำหรับประชาชน\n\n"
                            "กฎ:\n- ตอบเป็นภาษาไทยเสมอ\n- ใช้ Markdown formatting (หัวข้อ, bullet points, ตัวหนา) ให้อ่านง่าย\n"
                            "- อ้างอิงชื่อหน่วยงานที่เป็นแหล่งข้อมูลในคำตอบ\n- ห้ามเพิ่มข้อมูลที่ไม่มีในแหล่งข้อมูลที่ให้มา\n"
                            "- จบคำตอบด้วยข้อแนะนำเพิ่มเติมหากเหมาะสม"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f'คำถามจากประชาชน: "{body.query}"\n\nข้อมูลที่สืบค้นได้จากหน่วยงานราชการ:\n\n{agency_context}\n\nกรุณาสังเคราะห์ข้อมูลข้างต้นเป็นคำตอบที่ครบถ้วนและเข้าใจง่ายสำหรับประชาชน',
                    },
                ],
            )
            combined_answer = response.choices[0].message.content or "\n\n---\n\n".join(r["data"]["answer"] for r in results)
        except Exception as e:
            print(f"[AI synthesis error]: {e}")
            combined_answer = "\n\n---\n\n".join(r["data"]["answer"] for r in results)
    else:
        combined_answer = "\n\n---\n\n".join(r["data"]["answer"] for r in results)

    agent_steps.append({"icon": "📝", "label": "สังเคราะห์คำตอบเสร็จสิ้น", "status": "done"})

    all_references = [
        {"agency": r["agencyName"], **ref}
        for r in results
        for ref in r["data"]["references"]
    ]

    confidence_values = [r["data"]["confidence"] for r in results]
    avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0

    return {
        "success": True,
        "data": {
            "answer": combined_answer,
            "references": all_references,
            "agentSteps": agent_steps,
            "agencies": [
                {"id": a, "name": AGENCY_NAME_MAP[a], "icon": AGENCY_ICON_MAP[a]}
                for a in target_agencies
            ],
            "confidence": round(avg_confidence, 2),
        },
        "responseTime": int((time.time() - start) * 1000),
    }


@router.post("/agency/{agency_id}")
async def query_single_agency(agency_id: str, body: ChatRequest):
    if agency_id not in AGENCY_NAME_MAP:
        raise HTTPException(status_code=404, detail="Agency not found")
    await asyncio.sleep(0.4 + random.random() * 0.3)
    return query_agency(agency_id, body.query)
