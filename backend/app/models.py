"""
SQLAlchemy ORM models matching the existing Supabase PostgreSQL schema.
All tables are in the 'public' schema.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Any
from sqlalchemy import (
    String, Boolean, Integer, Text, ForeignKey,
    ARRAY, UniqueConstraint, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    agencies: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="success")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_time: Mapped[Optional[str]] = mapped_column(Text)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, server_default=func.now())

    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_conversations_created_at", "created_at"),
        Index("idx_conversations_user_id", "user_id"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_steps: Mapped[Optional[Any]] = mapped_column(JSONB)
    sources: Mapped[Optional[Any]] = mapped_column(JSONB)
    rating: Mapped[Optional[str]] = mapped_column(Text)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("idx_messages_conversation_id", "conversation_id"),
    )


class Agency(Base):
    __tablename__ = "agencies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    short_name: Mapped[str] = mapped_column(Text, nullable=False)
    logo: Mapped[str] = mapped_column(Text, nullable=False, default="🏢")
    connection_type: Mapped[str] = mapped_column(Text, nullable=False, default="API")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data_scope: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    total_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    color: Mapped[str] = mapped_column(Text, nullable=False, default="hsl(213 70% 45%)")
    endpoint_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    api_key_name: Mapped[Optional[str]] = mapped_column(Text)
    auth_method: Mapped[str] = mapped_column(Text, nullable=False, default="api_key")
    auth_header: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rate_limit_rpm: Mapped[Optional[int]] = mapped_column(Integer)
    request_format: Mapped[str] = mapped_column(Text, nullable=False, default="json")
    api_endpoints: Mapped[Optional[Any]] = mapped_column(JSONB, default=list)
    response_schema: Mapped[Optional[Any]] = mapped_column(JSONB, default=list)
    api_spec_raw: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, server_default=func.now(), onupdate=func.now())

    connection_logs: Mapped[List["ConnectionLog"]] = relationship("ConnectionLog", back_populates="agency", cascade="all, delete-orphan")


class ConnectionLog(Base):
    __tablename__ = "connection_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(Text, nullable=False, default="call")
    connection_type: Mapped[str] = mapped_column(Text, nullable=False, default="API")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="success")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, server_default=func.now())

    agency: Mapped["Agency"] = relationship("Agency", back_populates="connection_logs")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    auth_provider: Mapped[str] = mapped_column(Text, nullable=False, default="email")
    oauth_provider_id: Mapped[Optional[str]] = mapped_column(Text)
    last_sign_in_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata: Mapped[Optional[Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, server_default=func.now())


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "role", name="user_roles_user_id_role_key"),
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    permission: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("role", "permission", name="role_permissions_role_permission_key"),
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    scopes: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    last_used_ip: Mapped[Optional[str]] = mapped_column(Text)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    revoked_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_api_keys_user_id_active", "user_id", postgresql_where="revoked_at IS NULL"),
        Index("idx_api_keys_key_hash", "key_hash", postgresql_where="revoked_at IS NULL"),
    )
