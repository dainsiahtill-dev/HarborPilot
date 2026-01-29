from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

EventKind = Literal["action", "observation"]
Actor = Literal["PM", "Director", "Reviewer", "QA", "System", "Tooling"]
Phase = Literal[
    "handoff",
    "receipt",
    "tool_plan",
    "tool_exec",
    "evidence",
    "patch_plan",
    "apply",
    "rollback",
    "review",
    "qa",
    "gap_review",
    "memory",
    "done",
]


class EventRef(BaseModel):
    task_id: Optional[str] = None
    task_fingerprint: Optional[str] = None
    run_id: Optional[str] = None
    pm_iteration: Optional[int] = None
    director_iteration: Optional[int] = None
    phase: Optional[Phase] = None
    files: Optional[List[str]] = None
    evidence_path: Optional[str] = None
    trajectory_path: Optional[str] = None


class Truncation(BaseModel):
    truncated: bool = False
    reason: Optional[str] = None
    original_bytes: Optional[int] = None
    kept_bytes: Optional[int] = None
    original_lines: Optional[int] = None
    kept_lines: Optional[int] = None


class EventBase(BaseModel):
    schema_version: int = 1
    ts: str
    ts_epoch: float
    seq: int
    event_id: str
    kind: EventKind
    actor: Actor
    name: str
    refs: EventRef = Field(default_factory=EventRef)
    summary: str = ""
    meta: Dict[str, Any] = Field(default_factory=dict)


class ActionEvent(EventBase):
    kind: Literal["action"] = "action"
    input: Dict[str, Any] = Field(default_factory=dict)


class ObservationEvent(EventBase):
    kind: Literal["observation"] = "observation"
    ok: bool = True
    output: Dict[str, Any] = Field(default_factory=dict)
    truncation: Truncation = Field(default_factory=Truncation)
    duration_ms: Optional[int] = None
    error: Optional[str] = None
