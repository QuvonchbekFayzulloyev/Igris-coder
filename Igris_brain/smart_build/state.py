"""§21 State Machine — build session holat boshqaruvchisi."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class BuildState(str, Enum):
    """Build session holatlari."""
    RECEIVED = "received"
    ANALYZING = "analyzing"
    DISCOVERING = "discovering"
    MAPPING = "mapping"
    PLANNING = "planning"
    PLAN_VALIDATED = "plan_validated"
    IMPLEMENTING = "implementing"
    BUILDING = "building"
    TESTING = "testing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


# Valid state transitions
VALID_TRANSITIONS: dict[BuildState, set[BuildState]] = {
    BuildState.RECEIVED: {BuildState.ANALYZING, BuildState.CANCELLED},
    BuildState.ANALYZING: {BuildState.DISCOVERING, BuildState.FAILED, BuildState.CANCELLED},
    BuildState.DISCOVERING: {BuildState.MAPPING, BuildState.FAILED, BuildState.CANCELLED},
    BuildState.MAPPING: {BuildState.PLANNING, BuildState.FAILED, BuildState.CANCELLED},
    BuildState.PLANNING: {BuildState.PLAN_VALIDATED, BuildState.FAILED, BuildState.CANCELLED},
    BuildState.PLAN_VALIDATED: {BuildState.IMPLEMENTING, BuildState.FAILED, BuildState.CANCELLED},
    BuildState.IMPLEMENTING: {BuildState.BUILDING, BuildState.RECOVERING, BuildState.FAILED, BuildState.CANCELLED},
    BuildState.BUILDING: {BuildState.TESTING, BuildState.RECOVERING, BuildState.FAILED, BuildState.CANCELLED},
    BuildState.TESTING: {BuildState.VERIFYING, BuildState.RECOVERING, BuildState.FAILED, BuildState.CANCELLED},
    BuildState.VERIFYING: {BuildState.COMPLETED, BuildState.RECOVERING, BuildState.FAILED, BuildState.CANCELLED},
    BuildState.RECOVERING: {BuildState.IMPLEMENTING, BuildState.BUILDING, BuildState.TESTING, BuildState.FAILED},
    BuildState.COMPLETED: set(),
    BuildState.FAILED: {BuildState.RECEIVED},  # qayta boshlash mumkin
    BuildState.PAUSED: {BuildState.IMPLEMENTING, BuildState.BUILDING, BuildState.TESTING, BuildState.CANCELLED},
    BuildState.CANCELLED: set(),
}


@dataclass
class BuildStep:
    """Bitta build qadami."""
    step_id: str
    description: str
    state: str = "pending"  # pending, running, completed, failed, skipped
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    evidence: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "state": self.state,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "evidence_count": len(self.evidence),
        }


@dataclass
class BuildSession:
    """Build session — bitta vazifa uchun to'liq kontekst."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    task: str = ""
    state: BuildState = BuildState.RECEIVED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    # Steps
    steps: list[BuildStep] = field(default_factory=list)
    current_step: Optional[str] = None
    # Context
    project_root: str = ""
    project_type: str = ""
    language: str = ""
    framework: str = ""
    # Evidence
    evidence: list[dict] = field(default_factory=list)
    # Error tracking
    error_count: int = 0
    max_retries: int = 3
    last_error: str = ""
    # Results
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    tests_passed: int = 0
    tests_failed: int = 0
    # Final
    final_status: str = ""  # SUCCESS, FAILED, PARTIAL, UNKNOWN
    final_report: Optional[dict] = None

    def transition(self, new_state: BuildState) -> bool:
        """State o'tish — faqat valid bo'lsa."""
        valid = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in valid:
            return False
        self.state = new_state
        self.updated_at = time.time()
        return True

    def add_step(self, description: str) -> BuildStep:
        """Yangi step qo'shish."""
        step = BuildStep(
            step_id=f"step_{len(self.steps) + 1}",
            description=description,
        )
        self.steps.append(step)
        self.current_step = step.step_id
        return step

    def get_step(self, step_id: str) -> Optional[BuildStep]:
        """Step topish."""
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None

    def add_evidence(self, evidence_type: str, data: dict) -> None:
        """Evidence qo'shish."""
        self.evidence.append({
            "type": evidence_type,
            "data": data,
            "timestamp": time.time(),
        })

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "task": self.task,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step,
            "project_root": self.project_root,
            "project_type": self.project_type,
            "language": self.language,
            "framework": self.framework,
            "evidence_count": len(self.evidence),
            "error_count": self.error_count,
            "files_created": len(self.files_created),
            "files_modified": len(self.files_modified),
            "files_deleted": len(self.files_deleted),
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "final_status": self.final_status,
        }

    def resume(self) -> bool:
        """Poused session'ni davom ettirish."""
        if self.state == BuildState.PAUSED:
            # Qaysi step'da to'xtaganini aniqlamiz
            for step in self.steps:
                if step.state == "pending":
                    self.current_step = step.step_id
                    return True
        return False

    def save_state(self) -> dict:
        """State ni saqlash — interruption uchun."""
        return {
            "session_id": self.session_id,
            "task": self.task,
            "state": self.state.value,
            "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step,
            "evidence": self.evidence[-10:],  # oxirgi 10 ta
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "files_deleted": self.files_deleted,
        }

    @classmethod
    def load_state(cls, data: dict) -> "BuildSession":
        """State ni yuklash — resume uchun."""
        session = cls(
            session_id=data.get("session_id", ""),
            task=data.get("task", ""),
            state=BuildState(data.get("state", "received")),
            current_step=data.get("current_step"),
        )
        for s_data in data.get("steps", []):
            step = BuildStep(
                step_id=s_data["step_id"],
                description=s_data["description"],
                state=s_data.get("state", "pending"),
                error=s_data.get("error"),
            )
            session.steps.append(step)
        session.evidence = data.get("evidence", [])
        session.files_created = data.get("files_created", [])
        session.files_modified = data.get("files_modified", [])
        session.files_deleted = data.get("files_deleted", [])
        return session
