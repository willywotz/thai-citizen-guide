"""ReBAC tuples: (subject, relation, object) — minimal Zanzibar-style storage."""
from tortoise import fields
from tortoise.models import Model

from app.utils import generate_uuid


class Relationship(Model):
    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    subject_type = fields.CharField(max_length=20)   # user
    subject_id = fields.UUIDField()
    relation = fields.CharField(max_length=30)       # owner | viewer
    object_type = fields.CharField(max_length=30)    # agency | conversation
    object_id = fields.UUIDField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "relationships"
        unique_together = (("subject_type", "subject_id", "relation", "object_type", "object_id"),)
