"""
Compiled LangGraph for the Thai citizen AI chat pipeline.

Graph flow:
  detect_agencies → fetch_configs → fetch_agency_data → synthesize_answer

The graph is compiled once at startup and invoked per request.
DB session is injected via partial application of fetch_configs.
"""
from functools import partial
from typing import Any
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.state import ChatState
from app.graph.nodes import (
    node_detect_agencies,
    node_fetch_agency_configs,
    node_fetch_agency_data,
    node_synthesize_answer,
)


def build_graph(db: AsyncSession) -> Any:
    """
    Build and compile a LangGraph for a single request.
    db is injected so nodes can query the DB.
    """
    fetch_configs_with_db = partial(node_fetch_agency_configs, db=db)

    builder = StateGraph(ChatState)
    builder.add_node("detect_agencies", node_detect_agencies)
    builder.add_node("fetch_configs", fetch_configs_with_db)
    builder.add_node("fetch_agency_data", node_fetch_agency_data)
    builder.add_node("synthesize_answer", node_synthesize_answer)

    builder.set_entry_point("detect_agencies")
    builder.add_edge("detect_agencies", "fetch_configs")
    builder.add_edge("fetch_configs", "fetch_agency_data")
    builder.add_edge("fetch_agency_data", "synthesize_answer")
    builder.add_edge("synthesize_answer", END)

    return builder.compile()


async def run_chat_pipeline(query: str, db: AsyncSession) -> ChatState:
    """Run the full chat pipeline for a query. Returns the final state."""
    graph = build_graph(db)
    initial_state: ChatState = {
        "query": query,
        "target_agencies": [],
        "agency_configs": [],
        "agency_results": [],
        "synthesized_answer": None,
        "agent_steps": [],
        "references": [],
        "confidence": 0.8,
    }
    final_state = await graph.ainvoke(initial_state)
    return final_state
