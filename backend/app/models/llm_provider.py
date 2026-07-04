import uuid

from tortoise import fields
from tortoise.models import Model


class LlmProvider(Model):
    id = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    name = fields.CharField(max_length=50, unique=True)
    base_url = fields.CharField(max_length=500)
    api_key = fields.TextField(default="")
    auth_header = fields.CharField(max_length=100, default="Authorization")
    auth_scheme = fields.CharField(max_length=50, default="Bearer")
    timeout_seconds = fields.FloatField(default=60.0)
    request_usage = fields.BooleanField(default=False)
    rate_limit_rps = fields.IntField(null=True)
    rate_limit_rpm = fields.IntField(null=True)
    max_queue_size = fields.IntField(default=50)
    enabled = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "llm_providers"
