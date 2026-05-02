"""
ConnectionLog — records every agency connection test or query attempt.
"""

import uuid

from tortoise import fields, models
from app.utils import generate_uuid


class ConnectionLog(models.Model):
    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    agency: fields.ForeignKeyRelation = fields.ForeignKeyField(
        "models.Agency",
        related_name="connection_logs",
        on_delete=fields.CASCADE,
        null=True,
    )
    action = fields.CharField(max_length=50, default="test")   # test | query
    connection_type = fields.CharField(max_length=20)          # MCP | API | A2A
    status = fields.CharField(max_length=20)                   # success | error
    latency_ms = fields.IntField(default=0)
    detail = fields.TextField(default="")
    created_at = fields.DatetimeField(auto_now_add=True)

    request_body = fields.TextField(default="", null=True)
    response_body = fields.TextField(default="", null=True)

    class Meta:
        table = "connection_logs"
        ordering = ["-created_at"]
