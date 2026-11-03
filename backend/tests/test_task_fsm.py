import pytest
from app.core.errors import InvalidStateTransitionError
from app.domain.task_fsm import TaskFSM, TaskStatus, TaskStateGuard


def test_task_fsm_legal_transitions():
    # pending -> assigned -> in_progress -> in_review -> done
    assert TaskFSM.can_transition(TaskStatus.PENDING, TaskStatus.ASSIGNED)
    assert TaskFSM.can_transition(TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS)
    assert TaskFSM.can_transition(TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW)
    assert TaskFSM.can_transition(TaskStatus.IN_REVIEW, TaskStatus.REVIEWING)
    assert TaskFSM.can_transition(TaskStatus.REVIEWING, TaskStatus.DONE)
    assert TaskFSM.can_transition(TaskStatus.REVIEWING, TaskStatus.REVISION_REQUESTED)
    assert TaskFSM.can_transition(TaskStatus.IN_REVIEW, TaskStatus.DONE)

    # in_progress -> blocked -> in_progress
    assert TaskFSM.can_transition(TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED)
    assert TaskFSM.can_transition(TaskStatus.BLOCKED, TaskStatus.IN_PROGRESS)

    # in_progress -> integrating -> in_review
    assert TaskFSM.can_transition(TaskStatus.IN_PROGRESS, TaskStatus.INTEGRATING)
    assert TaskFSM.can_transition(TaskStatus.INTEGRATING, TaskStatus.IN_REVIEW)

    # in_review -> revision_requested -> in_progress
    assert TaskFSM.can_transition(TaskStatus.IN_REVIEW, TaskStatus.REVISION_REQUESTED)
    assert TaskFSM.can_transition(TaskStatus.REVISION_REQUESTED, TaskStatus.IN_PROGRESS)

    # non-terminal -> cancelled
    assert TaskFSM.can_transition(TaskStatus.PENDING, TaskStatus.CANCELLED)
    assert TaskFSM.can_transition(TaskStatus.ASSIGNED, TaskStatus.CANCELLED)
    assert TaskFSM.can_transition(TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED)
    assert TaskFSM.can_transition(TaskStatus.IN_REVIEW, TaskStatus.CANCELLED)


def test_task_fsm_illegal_transitions_raise():
    # Direct jump from pending to done is illegal
    with pytest.raises(InvalidStateTransitionError):
        TaskFSM.validate_transition(TaskStatus.PENDING, TaskStatus.DONE)

    # Direct jump from pending to in_progress is illegal
    with pytest.raises(InvalidStateTransitionError):
        TaskFSM.validate_transition(TaskStatus.PENDING, TaskStatus.IN_PROGRESS)


def test_task_fsm_terminal_states_cannot_transition():
    terminal_states = [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED]
    for term in terminal_states:
        assert TaskFSM.is_terminal(term)
        for target in TaskStatus:
            with pytest.raises(InvalidStateTransitionError):
                TaskFSM.validate_transition(term, target)


def test_task_fsm_is_ready():
    # Only assigned status can be ready
    assert not TaskFSM.is_ready(TaskStatus.PENDING, [])
    assert not TaskFSM.is_ready(TaskStatus.IN_PROGRESS, [TaskStatus.DONE])

    # Assigned with no deps is ready
    assert TaskFSM.is_ready(TaskStatus.ASSIGNED, [])

    # Assigned with all deps DONE is ready
    assert TaskFSM.is_ready(TaskStatus.ASSIGNED, [TaskStatus.DONE, TaskStatus.DONE])

    # Assigned with pending/in_progress dep is not ready
    assert not TaskFSM.is_ready(TaskStatus.ASSIGNED, [TaskStatus.DONE, TaskStatus.IN_PROGRESS])


def test_task_fsm_delegation_guards():
    guards = TaskStateGuard(max_depth=4, max_children=8)

    # Within limits: ok
    TaskFSM.validate_delegation_guard(
        current_depth=2,
        existing_children_count=3,
        new_children_count=2,
        guards=guards,
    )

    # Exceeding depth: raises
    with pytest.raises(InvalidStateTransitionError, match="Cannot delegate at depth 4"):
        TaskFSM.validate_delegation_guard(
            current_depth=4,
            existing_children_count=0,
            new_children_count=1,
            guards=guards,
        )

    # Exceeding max children: raises
    with pytest.raises(InvalidStateTransitionError, match="Exceeds max children limit"):
        TaskFSM.validate_delegation_guard(
            current_depth=1,
            existing_children_count=6,
            new_children_count=3,
            guards=guards,
        )
