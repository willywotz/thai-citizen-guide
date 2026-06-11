from datetime import datetime
import uuid
from .uuid7 import generate_uuid7
import pytz
from app.config import settings


def get_tz():
    return pytz.timezone(settings.TIMEZONE)


def generate_uuid() -> uuid.UUID:
    return generate_uuid7()

def now() -> datetime:
    return datetime.now(get_tz())