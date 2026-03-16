from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
import uuid


class MessageIn(BaseModel):
    id: Optional[str] = None
    role: str
    content: str
    agentSteps: Optional[Any] = None
    sources: Optional[Any] = None
    rating: Optional[str] = None


class ConversationCreate(BaseModel):
    title: str = "สนทนาใหม่"
    preview: str = ""
    agencies: List[str] = []
    status: str = "success"
    responseTime: Optional[str] = None
    messages: List[MessageIn] = []


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    preview: str
    date: str
    agencies: List[str]
    status: str
    messageCount: int
    responseTime: Optional[str] = None


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    agent_steps: Optional[Any] = None
    sources: Optional[Any] = None
    rating: Optional[str] = None
    feedback_text: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RatingUpdate(BaseModel):
    rating: str  # 'up' | 'down'
    feedback_text: Optional[str] = None
