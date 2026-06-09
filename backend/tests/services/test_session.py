from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.fixture
def mock_conversation():
    conv = MagicMock()
    conv.id = "conv-123"
    conv.external_session_id = None
    conv.save = AsyncMock()
    return conv


@pytest.fixture
def mock_first_message():
    msg = MagicMock()
    msg.content = "What documents do I need?"
    return msg


@pytest.mark.asyncio
async def test_no_op_when_session_already_warmed(mock_conversation):
    """If external_session_id is set, function returns immediately without DB or HTTP calls."""
    mock_conversation.external_session_id = "existing-session"

    with patch("app.services.session.Message") as MockMessage:
        from app.services.session import ensure_session_warmed
        await ensure_session_warmed(mock_conversation, "http://onechat/v3", "http://mcp/")

    MockMessage.filter.assert_not_called()
    mock_conversation.save.assert_not_called()


@pytest.mark.asyncio
async def test_no_op_when_no_first_message(mock_conversation):
    """If conversation has no user messages, function returns without calling OneChat."""
    mock_qs = MagicMock()
    mock_qs.order_by = MagicMock(return_value=MagicMock(first=AsyncMock(return_value=None)))

    with patch("app.services.session.Message") as MockMessage:
        MockMessage.filter.return_value = mock_qs
        from app.services.session import ensure_session_warmed
        await ensure_session_warmed(mock_conversation, "http://onechat/v3", "http://mcp/")

    mock_conversation.save.assert_not_called()


@pytest.mark.asyncio
async def test_warms_session_and_stores_session_id(mock_conversation, mock_first_message):
    """Replays first message to OneChat, stores returned session_id on conversation."""
    mock_qs = MagicMock()
    mock_qs.order_by = MagicMock(
        return_value=MagicMock(first=AsyncMock(return_value=mock_first_message))
    )

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": {"session_id": "warmed-session-abc"}}

    with patch("app.services.session.Message") as MockMessage, \
         patch("app.services.session.httpx.AsyncClient") as MockClient:

        MockMessage.filter.return_value = mock_qs
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services.session import ensure_session_warmed
        await ensure_session_warmed(mock_conversation, "http://onechat/v3", "http://mcp/")

    mock_client_instance.post.assert_called_once_with(
        "http://onechat/v3",
        json={
            "query": "What documents do I need?",
            "mcp_endpoint_url": "http://mcp/",
            "session_id": "conv-123",
        },
    )
    assert mock_conversation.external_session_id == "warmed-session-abc"
    mock_conversation.save.assert_called_once_with(update_fields=["external_session_id"])


@pytest.mark.asyncio
async def test_falls_back_to_conversation_id_when_no_session_in_response(mock_conversation, mock_first_message):
    """If OneChat response has no session_id, falls back to conversation.id."""
    mock_qs = MagicMock()
    mock_qs.order_by = MagicMock(
        return_value=MagicMock(first=AsyncMock(return_value=mock_first_message))
    )

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": {}}

    with patch("app.services.session.Message") as MockMessage, \
         patch("app.services.session.httpx.AsyncClient") as MockClient:

        MockMessage.filter.return_value = mock_qs
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services.session import ensure_session_warmed
        await ensure_session_warmed(mock_conversation, "http://onechat/v3", "http://mcp/")

    assert mock_conversation.external_session_id == "conv-123"
