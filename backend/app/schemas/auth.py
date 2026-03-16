from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid


class ApiKeyCreate(BaseModel):
    name: str
    scopes: List[str]
    expires_at: Optional[str] = None


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: List[str]
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyOut):
    raw_key: str  # shown once


class UserRoleUpdate(BaseModel):
    action: str  # assign_role | remove_role | deactivate | activate | update_profile
    user_id: str
    role: Optional[str] = None
    is_active: Optional[bool] = None
    display_name: Optional[str] = None


class UserOut(BaseModel):
    id: str
    email: Optional[str] = None
    profile: Optional[dict] = None
    roles: List[str] = []
    last_sign_in_at: Optional[str] = None
    created_at: Optional[str] = None
