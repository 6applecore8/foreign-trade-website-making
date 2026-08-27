from __future__ import annotations

from dataclasses import dataclass


class GraphError(ValueError):
    pass


@dataclass(frozen=True)
class Node:
    id: str
    data: dict


class WorkflowGraph:
    def __init__(self, workflow: dict):
        raw_nodes = workflow.get("nodes", [])
        ids = [item.get("id") for item in raw_nodes]
        if not ids or any(not item for item in ids) or len(ids) != len(set(ids)):
            raise GraphError("node ids must be present and unique")
        self.nodes = {item["id"]: Node(item["id"], item) for item in raw_nodes}
        self.executable = {key for key, node in self.nodes.items() if node.data.get("type") != "orchestrator"}
        self.dependencies = {key: set() for key in self.executable}
        for edge in workflow.get("edges", []):
            if not isinstance(edge, list) or len(edge) != 2 or edge[0] not in self.nodes or edge[1] not in self.nodes:
                raise GraphError(f"invalid edge: {edge!r}")
            source, target = edge
            if source in self.executable and target in self.executable:
                self.dependencies[target].add(source)
        self.topological_order()

    def topological_order(self) -> list[str]:
        remaining = {node: set(deps) for node, deps in self.dependencies.items()}
        result: list[str] = []
        while remaining:
            ready = sorted(node for node, deps in remaining.items() if not deps)
            if not ready:
                raise GraphError(f"cycle among executable nodes: {sorted(remaining)}")
            result.extend(ready)
            for node in ready:
                remaining.pop(node)
            for deps in remaining.values():
                deps.difference_update(ready)
        return result
