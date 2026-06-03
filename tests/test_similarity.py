import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.services.similarity import find_similar_question


@pytest.mark.asyncio
async def test_find_similar_question_with_embedding_hit():
    """When vector similarity >= threshold, return the cached answer."""
    from backend.app.models.conversation import Message, Conversation

    with patch("backend.app.services.similarity._vector_search", new_callable=AsyncMock) as mock_vector:
        mock_user_msg = MagicMock()
        mock_user_msg.id = "user-msg-id"
        mock_user_msg.content = "วิธีต่อทะเบียนบ้าน"
        mock_user_msg.conversation_id = "conv-id"
        mock_vector.return_value = mock_user_msg

        mock_assistant_msg = MagicMock()
        mock_assistant_msg.content = "คำตอบเก่า"
        mock_assistant_msg.id = "asst-msg-id"

        mock_conv = MagicMock()
        mock_conv.status = "success"

        with patch.object(Message, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [mock_assistant_msg, None]  # first call for assistant msg
            with patch.object(Conversation, "get", new_callable=AsyncMock) as mock_conv_get:
                mock_conv_get.return_value = mock_conv

                result = await find_similar_question(
                    query="จะลงทะเบียนบ้านทำยังไง",
                    embedding=[0.1] * 384,
                )
                assert result is not None
                user_msg, asst_msg = result
                assert user_msg.content == "วิธีต่อทะเบียนบ้าน"
                assert asst_msg.content == "คำตอบเก่า"


@pytest.mark.asyncio
async def test_find_similar_question_no_hit():
    """When no similar question found, return None."""
    with patch("backend.app.services.similarity._vector_search", new_callable=AsyncMock) as mock_vector:
        mock_vector.return_value = None

        result = await find_similar_question(
            query="คำถามใหม่มากๆ",
            embedding=[0.1] * 384,
        )
        assert result is None


@pytest.mark.asyncio
async def test_find_similar_question_trigram_fallback():
    """When embedding is None, trigram search is used."""
    from backend.app.models.conversation import Message, Conversation

    with patch("backend.app.services.similarity._trigram_search", new_callable=AsyncMock) as mock_trigram:
        mock_user_msg = MagicMock()
        mock_user_msg.id = "user-msg-id"
        mock_user_msg.content = "วิธีต่อทะเบียนบ้าน"
        mock_user_msg.conversation_id = "conv-id"
        mock_trigram.return_value = mock_user_msg

        mock_assistant_msg = MagicMock()
        mock_assistant_msg.content = "คำตอบเก่า"

        mock_conv = MagicMock()
        mock_conv.status = "success"

        with patch.object(Message, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [mock_assistant_msg, None]
            with patch.object(Conversation, "get", new_callable=AsyncMock) as mock_conv_get:
                mock_conv_get.return_value = mock_conv

                result = await find_similar_question(
                    query="วิธีต่อทะเบียนบ้าน",
                    embedding=None,
                )
                assert result is not None
                mock_trigram.assert_called_once()