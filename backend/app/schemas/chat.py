import uuid

from pydantic import BaseModel
from typing import Any

class ChatRequest(BaseModel):
    query: str
    conversation_id: uuid.UUID | None = None

class ChatResponseData(BaseModel):
    answer: str
    references: list[dict[str, Any]]
    agentSteps: list[dict[str, Any]]
    agencies: list[dict[str, Any]]
    confidence: float

class ChatResponse(BaseModel):
    success: bool
    data: ChatResponseData
    conversation_id: uuid.UUID
    responseTime: int
    
    error: str | None = None