from datetime import datetime, timezone
import uuid
from .uuid7 import generate_uuid7

def generate_uuid() -> uuid.UUID:
    return generate_uuid7()

def now() -> datetime:
    return datetime.now(timezone.utc)