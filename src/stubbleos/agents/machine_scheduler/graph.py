"""LangGraph workflow for Machine Scheduler agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from stubbleos.agents.machine_scheduler.logic import run_machine_scheduler
from stubbleos.agents.machine_scheduler.schemas import MachineSchedulerState
from stubbleos.llm.base import LLMClient


def build_machine_scheduler_graph(
    llm: LLMClient | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    """Builds and compiles the Machine Scheduler LangGraph workflow."""

    async def solve_node(state: MachineSchedulerState) -> dict[str, Any]:
        output = await run_machine_scheduler(state.input, llm=llm)
        return {
            "output": output,
            "assignments": output.assignments,
            "explanation": output.explanation,
            "status": "completed",
        }

    builder = StateGraph(MachineSchedulerState)
    builder.add_node("solve", solve_node)
    builder.add_edge(START, "solve")
    builder.add_edge("solve", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)
