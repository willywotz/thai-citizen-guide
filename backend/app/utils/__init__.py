from datetime import datetime, timezone
import uuid
from .uuid7 import generate_uuid7
from tortoise.timezone import now as tortoise_now
import pytz

tz = pytz.timezone('Asia/Bangkok')

def generate_uuid() -> uuid.UUID:
    return generate_uuid7()

def now() -> datetime:
    return datetime.now(tz)
    # return datetime.now(timezone.utc)
    # return tortoise_now()

def to_bangkok_time(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # Assume naive datetimes are in UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)

def get_tz():
    return tz