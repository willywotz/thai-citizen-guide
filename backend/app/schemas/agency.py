from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
import uuid


class ApiEndpoint(BaseModel):
    method: str
    path: str
    description: str


class ResponseField(BaseModel):
    field: str
    type: str
    description: str
    example: Optional[str] = None


class AgencyBase(BaseModel):
    name: str
    short_name: str
    logo: str = "🏢"
    connection_type: str = "API"
    status: str = "active"
    description: str = ""
    data_scope: List[str] = []
    color: str = "hsl(213 70% 45%)"
    endpoint_url: str = ""
    api_key_name: Optional[str] = None
    auth_method: str = "api_key"
    auth_header: str = ""
    base_path: str = ""
    rate_limit_rpm: Optional[int] = None
    request_format: str = "json"
    api_endpoints: List[Any] = []
    response_schema: List[Any] = []
    api_spec_raw: Optional[str] = None


class AgencyCreate(AgencyBase):
    pass


class AgencyUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    logo: Optional[str] = None
    connection_type: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    data_scope: Optional[List[str]] = None
    color: Optional[str] = None
    endpoint_url: Optional[str] = None
    api_key_name: Optional[str] = None
    auth_method: Optional[str] = None
    auth_header: Optional[str] = None
    base_path: Optional[str] = None
    rate_limit_rpm: Optional[int] = None
    request_format: Optional[str] = None
    api_endpoints: Optional[List[Any]] = None
    response_schema: Optional[List[Any]] = None
    api_spec_raw: Optional[str] = None


class AgencyOut(AgencyBase):
    id: uuid.UUID
    total_calls: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectionTestRequest(BaseModel):
    connection_type: str
    endpoint_url: str


class ConnectionTestStep(BaseModel):
    step: int
    label: str
    status: str
    time: int


class ConnectionTestResult(BaseModel):
    success: bool
    protocol: str
    version: str
    steps: List[ConnectionTestStep]
    latency: str
    statusCode: Optional[int] = None
    statusText: Optional[str] = None
    server: Optional[str] = None
    contentType: Optional[str] = None
    error: Optional[str] = None
    capabilities: Optional[List[str]] = None
    agentCard: Optional[dict] = None
