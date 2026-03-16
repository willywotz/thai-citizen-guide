"""
LangGraph state definition for the Thai citizen AI chat pipeline.
"""
from typing import TypedDict, Optional, List, Any
from dataclasses import dataclass, field


@dataclass
class AgencyResult:
    agency_id: str
    agency_name: str
    agency_icon: str
    answer: str
    references: List[dict]
    confidence: float
    latency_ms: int


@dataclass
class AgentStep:
    icon: str
    label: str
    status: str  # 'pending' | 'active' | 'done'


class ChatState(TypedDict):
    # Input
    query: str

    # Routing
    target_agencies: List[str]

    # Agency configs fetched from DB (for schema guide)
    agency_configs: List[dict]

    # Results from agency handlers
    agency_results: List[AgencyResult]

    # LLM synthesis
    synthesized_answer: Optional[str]

    # Transparency
    agent_steps: List[AgentStep]

    # Final aggregates
    references: List[dict]
    confidence: float
