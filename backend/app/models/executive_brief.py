"""
ExecutiveBrief — persisted "AI Weekly Executive Brief" snapshots.

Append-only: each (scheduled or forced) regeneration inserts a row. The current
brief is the latest row by `generated_at`.
"""

from tortoise import fields, models

from app.utils import generate_uuid


class ExecutiveBrief(models.Model):
    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    content = fields.TextField(default="")
    status = fields.CharField(max_length=16, default="ok")  # ok | error
    generated_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "executive_briefs"
        ordering = ["-generated_at"]
