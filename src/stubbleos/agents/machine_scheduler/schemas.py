"""Schemas for Machine Scheduler agent."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.optimization.scheduler import (
    JobRequest,
    MachineResource,
    ScheduledAssignment,
    SchedulerConfig,
)

SchedulingMode = Literal["cpsat", "auction"]


class MachineSchedulerInput(BaseModel):
    """Input payload for machine scheduling operations."""

    model_config = ConfigDict(extra="forbid")

    jobs: list[JobRequest]
    machines: list[MachineResource]
    mode: SchedulingMode = "cpsat"
    config: SchedulerConfig = Field(default_factory=SchedulerConfig)
    current_hour: float = 0.0
    seed: int = 42
    request_explanation: bool = True


class MachineSchedulerOutput(BaseModel):
    """Output result from machine scheduling operations."""

    model_config = ConfigDict(extra="forbid")

    assignments: list[ScheduledAssignment]
    unassigned_job_ids: list[UUID]
    objective_value: float
    solver_status: str
    wall_time_seconds: float
    explanation: str
    audit_logs: list[dict[str, Any]] = Field(default_factory=list)
    mode_used: SchedulingMode


class MachineSchedulerState(BaseModel):
    """LangGraph execution state for Machine Scheduler."""

    model_config = ConfigDict(extra="forbid")

    input: MachineSchedulerInput
    output: MachineSchedulerOutput | None = None
    assignments: list[ScheduledAssignment] = Field(default_factory=list)
    explanation: str = ""
    status: str = "initialized"
