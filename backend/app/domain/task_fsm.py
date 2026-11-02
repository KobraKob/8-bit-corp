from enum import Enum
from typing import Set, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.errors import InvalidStateTransitionError


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    INTEGRATING = "integrating"
    IN_REVIEW = "in_review"
    REVISION_REQUESTED = "revision_requested"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES: Set[TaskStatus] = {
    TaskStatus.DONE,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}

# Legal transitions mapping: current_status -> set of allowed next_statuses
LEGAL_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
    TaskStatus.PENDING: {
        TaskStatus.ASSIGNED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.ASSIGNED: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.CANCELLED,
    },
    TaskStatus.IN_PROGRESS: {
        TaskStatus.BLOCKED,
        TaskStatus.INTEGRATING,
        TaskStatus.IN_REVIEW,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.BLOCKED: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.INTEGRATING: {
        TaskStatus.IN_REVIEW,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.IN_REVIEW: {
        TaskStatus.DONE,
        TaskStatus.REVISION_REQUESTED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.REVISION_REQUESTED: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    # Terminal states have no transitions out
    TaskStatus.DONE: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


class TaskStateGuard(BaseModel):
    max_depth: int = 4
    max_children: int = 8
    max_attempts: int = 3
    token_budget: int = 25000


class TaskFSM:
    """Pure, unit-tested Task State Machine enforcing state transitions and guards."""

    @staticmethod
    def is_terminal(status: TaskStatus) -> bool:
        return status in TERMINAL_STATUSES

    @staticmethod
    def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
        return target in LEGAL_TRANSITIONS.get(current, set())

    @staticmethod
    def validate_transition(current: TaskStatus, target: TaskStatus) -> None:
        if TaskFSM.is_terminal(current):
            raise InvalidStateTransitionError(
                f"Cannot transition out of terminal state '{current.value}' to '{target.value}'."
            )
        if not TaskFSM.can_transition(current, target):
            raise InvalidStateTransitionError(
                f"Illegal transition from '{current.value}' to '{target.value}'."
            )

    @staticmethod
    def is_ready(status: TaskStatus, dependency_statuses: List[TaskStatus]) -> bool:
        """A task is ready when status is assigned and every dependency is done."""
        if status != TaskStatus.ASSIGNED:
            return False
        return all(dep_status == TaskStatus.DONE for dep_status in dependency_statuses)

    @staticmethod
    def validate_delegation_guard(
        current_depth: int,
        existing_children_count: int,
        new_children_count: int,
        guards: TaskStateGuard,
    ) -> None:
        if current_depth >= guards.max_depth:
            raise InvalidStateTransitionError(
                f"Cannot delegate at depth {current_depth}. Max depth is {guards.max_depth}."
            )
        if existing_children_count + new_children_count > guards.max_children:
            raise InvalidStateTransitionError(
                f"Cannot create {new_children_count} child tasks. Exceeds max children limit of {guards.max_children}."
            )
