"""The /responses surface speaks OpenAI's error envelope, not the portal's."""

import pytest

from app.services.responses.errors import ResponsesApiError


def test_envelope_matches_openai_shape():
    err = ResponsesApiError("Unknown model 'gpt-5'.", param="model")
    assert err.status == 400
    assert err.envelope() == {
        "error": {
            "message": "Unknown model 'gpt-5'.",
            "type": "invalid_request_error",
            "param": "model",
            "code": None,
        }
    }


def test_not_found_carries_its_code_and_status():
    err = ResponsesApiError(
        "Previous response with id 'resp_abc' not found",
        code="previous_response_not_found", status=404,
    )
    assert err.status == 404
    assert err.envelope()["error"]["code"] == "previous_response_not_found"
    assert err.envelope()["error"]["param"] is None
