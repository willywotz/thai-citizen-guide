from unittest.mock import AsyncMock, patch, MagicMock
import pytest


def test_build_router_prompt_includes_agency_names():
    from app.services.chat.llm import build_router_prompt

    agencies = [
        {
            "id": "abc-123",
            "name": "กรมสรรพากร",
            "description": "ด้านภาษี",
            "connection_type": "API",
            "endpoint_url": "http://example.com",
            "data_scope": ["ภาษี", "VAT"],
        }
    ]
    result = build_router_prompt(agencies)

    assert "กรมสรรพากร" in result
    assert "abc-123" in result
    assert "ภาษี, VAT" in result


def test_build_router_prompt_empty_agencies():
    from app.services.chat.llm import build_router_prompt

    result = build_router_prompt([])
    assert "routes" in result
    assert "Available sources:" in result


@pytest.mark.asyncio
async def test_call_llm_raises_on_missing_key():
    from app.services.chat.llm import call_llm
    from app.config import settings

    with patch.object(settings, "PARSE_SPEC_API_KEY", ""):
        with pytest.raises(ValueError, match="Missing LLM API key"):
            await call_llm([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_call_llm_returns_message_on_success():
    from app.services.chat.llm import call_llm
    from app.config import settings

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "hello"}}]
    }

    with patch.object(settings, "PARSE_SPEC_API_KEY", "test-key"), \
         patch("app.services.chat.llm.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await call_llm([{"role": "user", "content": "hi"}])

    assert result == {"role": "assistant", "content": "hello"}


# ─── extract_tag tests (F6) ───────────────────────────────────────────────────

def test_extract_tag_present_strips_and_returns_value():
    from app.services.chat.llm import extract_tag

    text = "Hello <category>taxation</category> world"
    cleaned, value = extract_tag(text, "category")

    assert value == "taxation"
    assert "<category>" not in cleaned
    assert "Hello" in cleaned
    assert "world" in cleaned


def test_extract_tag_absent_returns_original_and_none():
    from app.services.chat.llm import extract_tag

    text = "No tag here at all"
    cleaned, value = extract_tag(text, "category")

    assert value is None
    assert cleaned == text


def test_extract_tag_multiline_content():
    from app.services.chat.llm import extract_tag

    text = "Before\n<category>\nline one\nline two\n</category>\nAfter"
    cleaned, value = extract_tag(text, "category")

    assert value == "line one\nline two"
    assert "<category>" not in cleaned
    assert "Before" in cleaned
    assert "After" in cleaned


def test_extract_tag_leaves_other_tags_intact():
    from app.services.chat.llm import extract_tag

    text = "Intro <references>[1,2]</references> body <category>tax</category> end"
    # Strip references first, then category (as chat_internal does).
    after_refs, refs_val = extract_tag(text, "references")
    after_cat, cat_val = extract_tag(after_refs, "category")

    assert refs_val == "[1,2]"
    assert cat_val == "tax"
    assert "<references>" not in after_cat
    assert "<category>" not in after_cat
    assert "Intro" in after_cat
    assert "body" in after_cat
    assert "end" in after_cat
