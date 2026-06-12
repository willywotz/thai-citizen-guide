"""Audit trail of sensitive admin/owner actions — who did what to what."""
from tortoise import fields
from tortoise.models import Model

from app.utils import generate_uuid


class AuditLog(Model):
    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    actor_id = fields.UUIDField(null=True)               # who performed it (null = system)
    actor_email = fields.CharField(max_length=255, null=True)  # denormalized — survives user deletion
    action = fields.CharField(max_length=50)             # e.g. agency.status_change
    object_type = fields.CharField(max_length=30, null=True)
    object_id = fields.CharField(max_length=64, null=True)
    detail = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "audit_logs"
        ordering = ["-created_at"]
