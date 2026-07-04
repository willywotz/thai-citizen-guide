import uuid

from tortoise import fields
from tortoise.models import Model


class LlmRoute(Model):
    id = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    purpose = fields.CharField(max_length=50, unique=True)
    provider = fields.ForeignKeyField(
        "models.LlmProvider", related_name="routes", on_delete=fields.RESTRICT
    )
    model = fields.CharField(max_length=200)
    timeout_override = fields.FloatField(null=True)
    enabled = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "llm_routes"
