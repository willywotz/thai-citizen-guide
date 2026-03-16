from pydantic import BaseModel
from typing import Optional, List, Any


class AgentStep(BaseModel):
    icon: str
    label: str
    status: str  # 'pending' | 'active' | 'done'
    detail: Optional[str] = None


class Reference(BaseModel):
    agency: str
    title: str
    url: str


class AgencyInfo(BaseModel):
    id: str
    name: str
    icon: str


class ChatRequest(BaseModel):
    query: str


class ChatResponseData(BaseModel):
    answer: str
    references: List[Reference]
    agentSteps: List[AgentStep]
    agencies: List[AgencyInfo]
    confidence: float


class ChatResponse(BaseModel):
    success: bool
    data: ChatResponseData
    responseTime: int


# Internal agency result from handlers
class AgencyResult(BaseModel):
    success: bool
    agency: str
    agencyName: str
    data: dict  # {answer, references, confidence}
    responseTime: int
