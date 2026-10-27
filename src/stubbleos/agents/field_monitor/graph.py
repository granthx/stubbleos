"""LangGraph definition for Field Monitor agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from stubbleos.agents.field_monitor.logic import (
    build_field_events,
    detect_field_states,
)
from stubbleos.agents.field_monitor.schemas import FieldMonitorState
from stubbleos.core.config import Settings
from stubbleos.core.events import EventBus
from stubbleos.data.repositories import ApprovalRepository

_background_tasks: set[Any] = set()


def build_field_monitor_graph(
    *,
    approval_repo: ApprovalRepository | None = None,
    event_bus: EventBus | None = None,
    settings: Settings | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """Builds and compiles the Field Monitor agent LangGraph."""

    def detection_node(state: FieldMonitorState) -> dict[str, Any]:
        output = detect_field_states(state.input, settings=settings)
        return {"output": output, "status": "detected"}

    def action_node(state: FieldMonitorState) -> dict[str, Any]:
        if state.output is None:
            return {"status": "error_no_output"}

        approvals_created = []
        emitted_count = 0

        for obs in state.output.observations:
            # Route low confidence transitions to approvals queue
            if obs.requires_approval and approval_repo is not None:
                appr = approval_repo.create(
                    kind="field_state_change",
                    subject_type="field",
                    subject_id=obs.field_id,
                    reason=obs.approval_reason or "Low confidence observation",
                    requested_by="field_monitor",
                    confidence=obs.confidence,
                    payload={"detected_state": obs.detected_state.value, "evidence": obs.evidence},
                )
                approvals_created.append(appr.id)

            # Emit events if event bus is connected
            if event_bus is not None:
                import asyncio

                events = build_field_events(obs)
                for ev in events:
                    try:
                        loop = asyncio.get_running_loop()
                        task = loop.create_task(
                            event_bus.emit(ev, source="field_monitor", district=state.input.district)
                        )
                        _background_tasks.add(task)
                        task.add_done_callback(_background_tasks.discard)
                    except RuntimeError:
                        asyncio.run(event_bus.emit(ev, source="field_monitor", district=state.input.district))
                    emitted_count += 1

        return {
            "created_approval_ids": approvals_created,
            "emitted_events_count": emitted_count,
            "status": "completed",
        }

    builder = StateGraph(FieldMonitorState)
    builder.add_node("detection", detection_node)
    builder.add_node("action", action_node)

    builder.set_entry_point("detection")
    builder.add_edge("detection", "action")
    builder.add_edge("action", END)

    cp = checkpointer if checkpointer is not None else MemorySaver()
    return builder.compile(checkpointer=cp)
