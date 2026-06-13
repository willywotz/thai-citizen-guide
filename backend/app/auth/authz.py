"""Layered authorization: RBAC (role) -> ReBAC (relationship) -> ABAC (attributes).

authorize() is the single decision point; routers depend on it instead of
require_admin + inline user_id filters. Deny overrides allow at the ABAC layer.
"""
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from app.models import Relationship
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    allowed: bool
    layer: str    # rbac | rebac | abac
    reason: str = ""


_ADMIN_ONLY = {"agency:change_status", "settings:edit", "user:manage", "agency:delete"}
# Read actions an auditor may perform globally (audit capability), independent of
# ownership. Writes (agency:edit, conversation:delete) still fall through to denial.
_AUDITOR_READ = {"conversation:read", "agency:read_logs"}

_RELATION_FOR = {
    "agency:edit": ("owner", "agency"),
    "agency:read_logs": ("owner", "agency"),
    "conversation:read": ("owner", "conversation"),
    "conversation:delete": ("owner", "conversation"),
}


async def grant(subject_id, relation: str, object_type: str, object_id) -> None:
    await Relationship.get_or_create(
        subject_type="user", subject_id=subject_id, relation=relation,
        object_type=object_type, object_id=object_id,
    )


async def has_relation(subject_id, relation: str, object_type: str, object_id) -> bool:
    return await Relationship.filter(
        subject_type="user", subject_id=subject_id, relation=relation,
        object_type=object_type, object_id=object_id,
    ).exists()


def _abac(user: User, action: str, resource: Any) -> Decision | None:
    if action == "agency:edit" and getattr(resource, "status", None) == "active":
        return Decision(False, "abac", "active agencies are edited via admin approval")
    return None


async def authorize(user: User, action: str, resource: Any) -> Decision:
    # Inactive users are denied first (ABAC), admin included.
    if not user.is_active:
        return _log(user, action, Decision(False, "abac", "user inactive"))

    # RBAC
    if user.role == "admin":
        return _log(user, action, Decision(True, "rbac", "admin"))
    # Auditors have global read-only access (audit capability); writes still fall through to denial.
    if user.role == "auditor" and action in _AUDITOR_READ:
        return _log(user, action, Decision(True, "rbac", "auditor read-only"))
    if action in _ADMIN_ONLY:
        return _log(user, action, Decision(False, "rbac", "admin required"))

    rel = _RELATION_FOR.get(action)
    if rel is None:
        return _log(user, action, Decision(False, "rbac", f"unknown action {action}"))
    relation, object_type = rel
    if object_type == "conversation":
        owned = str(getattr(resource, "user_id", "")) == str(user.id)
    else:
        owned = await has_relation(user.id, relation, object_type, resource.id)
    if not owned:
        return _log(user, action, Decision(False, "rebac", f"missing {relation} on {object_type}"))

    deny = _abac(user, action, resource)
    if deny:
        return _log(user, action, deny)
    return Decision(True, "rebac", "")


async def authorize_or_403(user: User, action: str, resource: Any) -> None:
    d = await authorize(user, action, resource)
    if not d.allowed:
        raise HTTPException(status_code=403, detail=d.reason or "Forbidden")


def _log(user: User, action: str, d: Decision) -> Decision:
    if not d.allowed or d.reason == "admin":
        logger.info("authz %s user=%s action=%s layer=%s reason=%s",
                    "ALLOW" if d.allowed else "DENY", user.id, action, d.layer, d.reason)
    return d
