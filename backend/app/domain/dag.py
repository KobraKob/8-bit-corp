from typing import Dict, List, Set
from app.core.errors import CycleDetectedError


def detect_cycles_in_subtasks(
    new_subtasks: List[Dict[str, any]],
    existing_dependencies: Dict[str, List[str]] = None,
) -> None:
    """Validates that newly proposed subtasks and their depends_on declarations do not form a cycle.
    
    `new_subtasks` is a list of subtasks, each having an identifier/temp_id or title, and `depends_on`.
    `existing_dependencies` maps existing task_id to its dependencies.
    """
    graph: Dict[str, Set[str]] = {}
    if existing_dependencies:
        for node, deps in existing_dependencies.items():
            graph[node] = set(deps)

    # Add new subtask nodes and edges
    for st in new_subtasks:
        node_id = st.get("id") or st.get("temp_id") or st.get("title")
        deps = st.get("depends_on", [])
        if node_id not in graph:
            graph[node_id] = set()
        for dep in deps:
            graph[node_id].add(dep)

    # Detect cycle using 3-color DFS
    # 0 = unvisited, 1 = visiting, 2 = visited
    state: Dict[str, int] = {node: 0 for node in graph}

    def dfs(node: str, path: List[str]) -> None:
        state[node] = 1
        path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in state:
                # External dependency not in local batch; cycle cannot loop through unknown external node unless it points back
                continue
            if state[neighbor] == 1:
                cycle_str = " -> ".join(path + [neighbor])
                raise CycleDetectedError(f"Cycle detected in subtask dependencies: {cycle_str}")
            if state[neighbor] == 0:
                dfs(neighbor, path)
        path.pop()
        state[node] = 2

    for node in graph:
        if state[node] == 0:
            dfs(node, [])
