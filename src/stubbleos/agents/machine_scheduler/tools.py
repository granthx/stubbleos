"""Tools for Machine Scheduler agent."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from stubbleos.llm.base import LLMClient


def create_scheduler_tools(llm: LLMClient | None = None) -> list[Any]:
    """Factory to instantiate machine scheduling tools."""

    @tool
    async def schedule_machinery(
        mode: str = "cpsat",
        current_hour: float = 0.0,
        request_explanation: bool = True,
    ) -> dict[str, Any]:
        """Runs the CP-SAT machine scheduler or Contract-Net auction on candidate jobs."""
        # Note: in graph workflows, jobs and machines are passed via state.
        return {
            "mode": mode,
            "current_hour": current_hour,
            "request_explanation": request_explanation,
            "status": "ready",
        }

    return [schedule_machinery]
