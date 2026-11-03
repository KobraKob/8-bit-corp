import pytest
from app.core.errors import CycleDetectedError
from app.domain.dag import detect_cycles_in_subtasks


def test_dag_valid_linear_dependencies():
    subtasks = [
        {"id": "task_1", "depends_on": []},
        {"id": "task_2", "depends_on": ["task_1"]},
        {"id": "task_3", "depends_on": ["task_2"]},
    ]
    # Should not raise
    detect_cycles_in_subtasks(subtasks)


def test_dag_valid_diamond_dependencies():
    subtasks = [
        {"id": "task_1", "depends_on": []},
        {"id": "task_2a", "depends_on": ["task_1"]},
        {"id": "task_2b", "depends_on": ["task_1"]},
        {"id": "task_3", "depends_on": ["task_2a", "task_2b"]},
    ]
    # Should not raise
    detect_cycles_in_subtasks(subtasks)


def test_dag_direct_cycle_detected():
    subtasks = [
        {"id": "task_1", "depends_on": ["task_2"]},
        {"id": "task_2", "depends_on": ["task_1"]},
    ]
    with pytest.raises(CycleDetectedError, match="Cycle detected"):
        detect_cycles_in_subtasks(subtasks)


def test_dag_indirect_cycle_detected():
    subtasks = [
        {"id": "A", "depends_on": ["B"]},
        {"id": "B", "depends_on": ["C"]},
        {"id": "C", "depends_on": ["A"]},
    ]
    with pytest.raises(CycleDetectedError, match="Cycle detected"):
        detect_cycles_in_subtasks(subtasks)


def test_dag_resolves_titles_when_detecting_cycles():
    subtasks = [
        {"id": "first", "title": "First", "depends_on": ["Second"]},
        {"id": "second", "title": "Second", "depends_on": ["First"]},
    ]
    with pytest.raises(CycleDetectedError, match="Cycle detected"):
        detect_cycles_in_subtasks(subtasks)


def test_dag_rejects_duplicate_titles():
    subtasks = [
        {"id": "first", "title": "Same title", "depends_on": []},
        {"id": "second", "title": "Same title", "depends_on": []},
    ]
    with pytest.raises(CycleDetectedError, match="Duplicate"):
        detect_cycles_in_subtasks(subtasks)
