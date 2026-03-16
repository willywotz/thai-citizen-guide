import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Float, Boolean, ForeignKey, Enum as SAEnum, ARRAY, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AppRole(enum.Enum):
    admin = "admin"
    user = "user"


# ---------------------------------------------------------------------------
# Users (custom auth — separate from Supabase auth.users)
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    reset_token: Mapped[str | None] = mapped_column(String(255))
    reset_token_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=utcnow)


# ---------------------------------------------------------------------------
# Profiles (mirrors Supabase auth.users via trigger)
# ---------------------------------------------------------------------------

class Profile(Base):
    __tablename__ = "profiles"

    # id references auth.users(id) — stored as UUID but no FK to keep SQLAlchemy
    # decoupled from Supabase's internal auth schema
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=utcnow)

    roles: Mapped[list["UserRole"]] = relationship(back_populates="profile", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# User Roles
# ---------------------------------------------------------------------------

class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[AppRole] = mapped_column(SAEnum(AppRole, name="app_role"), nullable=False)

    profile: Mapped["Profile"] = relationship(back_populates="roles")


# ---------------------------------------------------------------------------
# Agencies
# ---------------------------------------------------------------------------

class Agency(Base):
    __tablename__ = "agencies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100))
    logo: Mapped[str | None] = mapped_column(String(10))
    color: Mapped[str | None] = mapped_column(String(100))
    connection_type: Mapped[str] = mapped_column(String(50), server_default="API")
    status: Mapped[str] = mapped_column(String(50), server_default="active")
    description: Mapped[str | None] = mapped_column(Text)
    data_scope: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    total_calls: Mapped[int] = mapped_column(Integer, server_default="0")

    # API connection
    endpoint_url: Mapped[str | None] = mapped_column(Text)
    api_key_name: Mapped[str | None] = mapped_column(String(255))
    auth_method: Mapped[str | None] = mapped_column(String(100))
    auth_header: Mapped[str | None] = mapped_column(String(255))
    base_path: Mapped[str | None] = mapped_column(Text)
    rate_limit_rpm: Mapped[int | None] = mapped_column(Integer)
    request_format: Mapped[str | None] = mapped_column(String(100))

    # API spec / endpoints
    api_endpoints: Mapped[dict | None] = mapped_column(JSONB)
    api_spec_raw: Mapped[str | None] = mapped_column(Text)
    response_schema: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=utcnow)

    connection_logs: Mapped[list["ConnectionLog"]] = relationship(back_populates="agency", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    preview: Mapped[str | None] = mapped_column(Text)
    agencies: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(String(50), server_default="success")
    message_count: Mapped[int] = mapped_column(Integer, server_default="0")
    response_time: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_steps: Mapped[dict | None] = mapped_column(JSONB)
    sources: Mapped[dict | None] = mapped_column(JSONB)
    rating: Mapped[str | None] = mapped_column(String(10))
    feedback_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# Connection Logs
# ---------------------------------------------------------------------------

class ConnectionLog(Base):
    __tablename__ = "connection_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str | None] = mapped_column(String(100))
    connection_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str | None] = mapped_column(String(50))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agency: Mapped["Agency"] = relationship(back_populates="connection_logs")
