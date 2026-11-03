from typing import Any, Dict, List, Set

from app.core.errors import CycleDetectedError


def detect_cycles_in_subtasks(
    new_subtasks: List[Dict[str, Any]],
    existing_dependencies: Dict[str, List[str]] | None = None,
) -> None:
    """Validate the dependency graph using IDs, temporary IDs, and unique titles."""
    graph: Dict[str, Set[str]] = {
        node: set(dependencies)
        for node, dependencies in (existing_dependencies or {}).items()
    }
    alias_to_node: Dict[str, str] = {}

    for subtask in new_subtasks:
        node_id = subtask.get("id") or subtask.get("temp_id") or subtask.get("title")
        if not isinstance(node_id, str) or not node_id.strip():
            raise CycleDetectedError("Every delegated task requires an id, temp_id, or title.")
        if node_id in graph:
            raise CycleDetectedError(f"Duplicate subtask identifier: {node_id}")
        for alias in (subtask.get("id"), subtask.get("temp_id"), subtask.get("title")):
            if not alias:
                continue
            previous = alias_to_node.get(alias)
            if previous and previous != node_id:
                raise CycleDetectedError(f"Duplicate subtask identifier or title: {alias}")
            alias_to_node[alias] = node_id
        graph[node_id] = set()

    for subtask in new_subtasks:
        node_id = subtask.get("id") or subtask.get("temp_id") or subtask.get("title")
        dependencies = subtask.get("depends_on", [])
        if not isinstance(dependencies, list):
            raise CycleDetectedError(f"Dependencies for {node_id} must be a list.")
        for dependency in dependencies:
            if not isinstance(dependency, str) or not dependency.strip():
                raise CycleDetectedError(f"Invalid dependency reference in {node_id}.")
            graph[node_id].add(alias_to_node.get(dependency, dependency))

    state: Dict[str, int] = {node: 0 for node in graph}

    def visit(node: str, path: List[str]) -> None:
        state[node] = 1
        path.append(node)
        for neighbor in graph.get(node, set()):
            if neighbor not in state:
                continue
            if state[neighbor] == 1:
                raise CycleDetectedError("Cycle detected in subtask dependencies: " + " -> ".join(path + [neighbor]))
            if state[neighbor] == 0:
                visit(neighbor, path)
        path.pop()
        state[node] = 2

    for node in graph:
        if state[node] == 0:
            visit(node, [])
