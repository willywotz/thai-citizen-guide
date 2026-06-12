"""Per-call LLM token/cost accounting."""
from tortoise import fields
from tortoise.models import Model

from app.utils import generate_uuid


class LlmUsage(Model):
    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    model = fields.CharField(max_length=100)
    purpose = fields.CharField(max_length=30)  # router | synthesis | classification | embedding | brief | judge
    prompt_tokens = fields.IntField(default=0)
    completion_tokens = fields.IntField(default=0)
    cost_usd = fields.FloatField(null=True)
    user_id = fields.UUIDField(null=True)
    agency_id = fields.UUIDField(null=True)
    conversation_id = fields.UUIDField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "llm_usage"
        ordering = ["-created_at"]

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
