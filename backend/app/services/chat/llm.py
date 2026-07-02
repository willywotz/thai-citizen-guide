import logging

from app.config import settings
from app.models.conversation import Message
from app.services.embedding import encode_embedding, generate_embedding
from app.services.llm_client import openrouter_chat

logger = logging.getLogger(__name__)


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
    resp = await openrouter_chat(payload, purpose="classification")
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
