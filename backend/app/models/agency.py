import uuid
from enum import Enum

from tortoise import fields
from tortoise.models import Model
from app.utils import generate_uuid

class ConnectionType(str, Enum):
    MCP = "MCP"
    API = "API"
    A2A = "A2A"


class AgencyStatus(str, Enum):
    draft = "draft"
    active = "active"
    maintenance = "maintenance"
    disabled = "disabled"


class Agency(Model):
    """
    Government agency model.
    Mirrors the `agencies` table from the original Supabase schema.
    """

    id = fields.UUIDField(primary_key=True, default=generate_uuid)
    name = fields.CharField(max_length=255)
    short_name = fields.CharField(max_length=50, null=True)
    logo = fields.CharField(max_length=20, null=True)           # emoji icon
    description = fields.TextField(null=True)

    # Connection
    connection_type = fields.CharEnumField(
        ConnectionType, max_length=10, default=ConnectionType.API
    )
    status = fields.CharEnumField(
        AgencyStatus, max_length=20, default=AgencyStatus.active
    )
    # Set True when the health rule auto-set maintenance; lets only rule-set
    # maintenance be auto-reactivated. Cleared on every manual status change.
    auto_maintenance = fields.BooleanField(default=False)

    # Scope
    data_scope = fields.JSONField(default=list)                 # list[str]
    color = fields.CharField(max_length=50, null=True)

    # Endpoint configuration
    endpoint_url = fields.CharField(max_length=1000, null=True)
    auth_method = fields.CharField(max_length=50, null=True)
    auth_header = fields.CharField(max_length=100, null=True)
    base_path = fields.CharField(max_length=255, null=True)
    api_key_name = fields.CharField(max_length=100, null=True)
    rate_limit_rpm = fields.IntField(null=True)
    request_format = fields.CharField(max_length=50, null=True)

    # Schema / spec
    api_endpoints = fields.JSONField(default=list)              # list[ApiEndpoint]
    response_schema = fields.JSONField(default=list)            # list[ResponseField]
    api_spec_raw = fields.TextField(null=True)

    expected_payload = fields.JSONField(null=True)
    api_headers = fields.JSONField(null=True, default=list)              # list[ApiHeader]

    # Routing controls
    priority = fields.IntField(null=True)
    router_hint = fields.TextField(default="")
    dispatch_timeout_s = fields.IntField(null=True)
    mcp_tool_name = fields.CharField(max_length=255, null=True)

    # Metrics
    total_calls = fields.IntField(default=0)
    rating_up = fields.IntField(default=0)
    rating_down = fields.IntField(default=0)

    # Timestamps
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "agencies"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.short_name or self.name} ({self.connection_type})"
