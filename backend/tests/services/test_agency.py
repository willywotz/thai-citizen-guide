from unittest.mock import AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_parse_spec_raises_on_http_error():
    from app.services.agency import parse_spec
    from app.services.llm import LlmError

    with patch("app.services.llm.chat", AsyncMock(side_effect=LlmError("parse_spec: provider returned 429", status=429))):
        with pytest.raises(LlmError):
            await parse_spec("some spec text")
