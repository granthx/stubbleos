"""LangGraph workflow for Policy & Safety Guard."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from stubbleos.agents.policy_guard.logic import evaluate_policy
from stubbleos.agents.policy_guard.schemas import PolicyGuardState
from stubbleos.core.config import Settings
from stubbleos.data.repositories import ConsentRepository


def build_policy_guard_graph(
    consent_repo: ConsentRepository | None = None,
    settings: Settings | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles the Policy & Safety Guard LangGraph workflow."""

    def evaluate_node(state: PolicyGuardState) -> dict[str, Any]:
        result = evaluate_policy(state.request, consent_repo=consent_repo, settings=settings)
        return {
            "result": result,
            "is_allowed": result.is_allowed,
            "violations": result.violations,
        }

    builder = StateGraph(PolicyGuardState)
    builder.add_node("evaluate", evaluate_node)
    builder.add_edge(START, "evaluate")
    builder.add_edge("evaluate", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
