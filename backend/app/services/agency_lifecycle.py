"""Agency lifecycle transition rules — mirrors the frontend lifecycle.ts table."""

LEGAL_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["active", "disabled"],
    "active": ["maintenance", "disabled"],
    "maintenance": ["active", "disabled"],
    "disabled": ["active"],
}


def is_legal_transition(current: str, target: str) -> bool:
    return target in LEGAL_TRANSITIONS.get(current, [])
