from datetime import datetime
from zoneinfo import ZoneInfo
import uuid
from .uuid7 import generate_uuid7

tz = ZoneInfo("Asia/Bangkok")

def generate_uuid() -> uuid.UUID:
    return generate_uuid7()

def now() -> datetime:
    return datetime.now(tz)