from app.services.agency_lifecycle import LEGAL_TRANSITIONS, is_legal_transition


def test_legal_transition_matrix():
    assert LEGAL_TRANSITIONS["draft"] == ["active", "disabled"]
    assert LEGAL_TRANSITIONS["active"] == ["maintenance", "disabled"]
    assert LEGAL_TRANSITIONS["maintenance"] == ["active", "disabled"]
    assert LEGAL_TRANSITIONS["disabled"] == ["active"]


def test_is_legal_transition():
    assert is_legal_transition("draft", "active") is True
    assert is_legal_transition("disabled", "maintenance") is False
    assert is_legal_transition("active", "draft") is False
