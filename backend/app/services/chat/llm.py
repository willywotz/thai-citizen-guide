import logging

import httpx

from app.config import settings
from app.models.conversation import Message
from app.services.embedding import encode_embedding, generate_embedding

logger = logging.getLogger(__name__)


async def call_llm(messages: list[dict]) -> dict:
    if not settings.PARSE_SPEC_API_KEY:
        raise ValueError("Missing LLM API key")

    async with httpx.AsyncClient(timeout=settings.LLM_CALL_TIMEOUT) as client:
        resp = await client.post(
            settings.PARSE_SPEC_URL,
            headers={
                "apikey": settings.PARSE_SPEC_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "model": settings.PARSE_SPEC_LLM_MODEL,
                "messages": messages,
            },
        )
    if resp.status_code == 200:
        choices = resp.json().get("choices", [])
        if not choices:
            raise ValueError("LLM API returned empty choices")
        return choices[0].get("message", {})
    raise ValueError(f"LLM API error: {resp.status_code} {resp.text}")


def build_router_prompt(agencies: list[dict]) -> str:
    source_lines = []
    for ag in agencies:
        scope = ", ".join(ag.get("data_scope", []))
        source_lines.append(
            f'- {ag["name"]} (id: {ag["id"]}, type: {ag["connection_type"]}, '
            f'endpoint: {ag.get("endpoint_url", "")}): '
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


async def classify_message_category(message_id: str, query: str, answer: str) -> None:
    content = f"""\
คุณเป็นโมเดลภาษา LLM ที่เชี่ยวชาญด้านการวิเคราะห์ข้อความและการจัดหมวดหมู่คำถามในบริบทของการให้บริการข้อมูลภาครัฐไทย
โปรดวิเคราะห์คำถามของผู้ใช้และระบุหมวดหมู่ที่ตรงที่สุด 1 หมวด จากนี้: สอบถามข้อมูล | ตรวจสอบสถานะ | ขั้นตอนดำเนินการ | กฎหมาย/ระเบียบ
ตอบเป็นข้อความที่มีเพียงหมวดหมู่ที่วิเคราะห์ได้เท่านั้น เช่น:
ขั้นตอนดำเนินการ

ถ้าคำถามไม่ชัดเจนหรือไม่สามารถจัดหมวดหมู่ได้ ให้ตอบว่า "ไม่สามารถจัดหมวดหมู่ได้"

คำถาม: {query}

คำตอบ: {answer}
"""
    payload = {
        "model": settings.CLASSIFICATION_MODEL,
        "messages": [{"role": "user", "content": content}],
    }
    async with httpx.AsyncClient(timeout=settings.LLM_CALL_TIMEOUT) as client:
        resp = await client.post(
            settings.OPENROUTER_API_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
            json=payload,
        )
    try:
        category = resp.json()["choices"][0]["message"]["content"].strip()
        await Message.filter(id=message_id).update(category=category)
    except Exception as e:
        logger.error("Error classifying message category: %s", e)


async def store_embedding(message_id: str, query: str) -> None:
    embedding = await generate_embedding(query)
    if embedding is not None:
        encoded = encode_embedding(embedding)
        await Message.filter(id=message_id).update(embedding=encoded)
