from datetime import datetime, timezone
import uuid
from .uuid7 import generate_uuid7
from tortoise.timezone import now as tortoise_now
import pytz
from app.config import settings


def get_tz():
    return pytz.timezone(settings.TIMEZONE)


def generate_uuid() -> uuid.UUID:
    return generate_uuid7()

def now() -> datetime:
    return datetime.now(get_tz())

def to_bangkok_time(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(get_tz())