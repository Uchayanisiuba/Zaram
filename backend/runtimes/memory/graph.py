from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time


class EdgeType(str, Enum):
    CAUSAL = "causal"
    ASSOCIATIVE = "associative"
    TEMPORAL = "temporal"
    SIMILARITY = "similarity"
    CONTRADICTION = "contradiction"
    REFERENCE = "reference"


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryGraph:
    """Tracks relationships between memories.

    The graph stores nodes (memory record IDs) and directed edges
    (relationships between memories). Supports traversal, querying,
    and automatic relationship discovery.
    """

    def __init__(self):
        self._nodes: set[str] = set()
        self._edges: dict[str, list[GraphEdge]] = defaultdict(list)
        self._reverse_edges: dict[str, list[GraphEdge]] = defaultdict(list)
        self._edge_index: dict[tuple[str, str, str], GraphEdge] = {}
        self._stats = {
            "nodes": 0,
            "edges": 0,
            "edge_types": defaultdict(int),
        }

    def add_node(self, record_id: str) -> None:
        """Add a memory node to the graph."""
        self._nodes.add(record_id)
        self._stats["nodes"] = len(self._nodes)

    def remove_node(self, record_id: str) -> bool:
        """Remove a memory node and all its edges."""
        if record_id not in self._nodes:
            return False

        for edge in self._edges.get(record_id, []):
            self._edge_index.pop((edge.source_id, edge.target_id, edge.edge_type.value), None)
            self._stats["edges"] -= 1
            self._stats["edge_types"][edge.edge_type.value] -= 1
            target_edges = self._reverse_edges.get(edge.target_id, [])
            self._reverse_edges[edge.target_id] = [
                e for e in target_edges if e.source_id != record_id
            ]
        self._edges.pop(record_id, None)

        for edge in self._reverse_edges.get(record_id, []):
            self._edge_index.pop((edge.source_id, edge.target_id, edge.edge_type.value), None)
            self._stats["edges"] -= 1
            self._stats["edge_types"][edge.edge_type.value] -= 1
            source_edges = self._edges.get(edge.source_id, [])
            self._edges[edge.source_id] = [
                e for e in source_edges if e.target_id != record_id
            ]
        self._reverse_edges.pop(record_id, None)

        self._nodes.discard(record_id)
        self._stats["nodes"] = len(self._nodes)
        return True

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType = EdgeType.ASSOCIATIVE,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> GraphEdge:
        """Add a directed edge between two memory nodes."""
        self.add_node(source_id)
        self.add_node(target_id)

        key = (source_id, target_id, edge_type.value)
        if key in self._edge_index:
            existing = self._edge_index[key]
            existing.weight = max(existing.weight, weight)
            existing.created_at = time.time()
            if metadata:
                existing.metadata.update(metadata)
            return existing

        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            metadata=metadata or {},
        )
        self._edges[source_id].append(edge)
        self._reverse_edges[target_id].append(edge)
        self._edge_index[key] = edge
        self._stats["edges"] += 1
        self._stats["edge_types"][edge_type.value] += 1
        return edge

    def remove_edge(self, source_id: str, target_id: str, edge_type: EdgeType | None = None) -> bool:
        """Remove an edge between two nodes."""
        removed = False
        if edge_type:
            key = (source_id, target_id, edge_type.value)
            edge = self._edge_index.pop(key, None)
            if edge:
                self._edges[source_id] = [e for e in self._edges[source_id] if e.target_id != target_id or e.edge_type != edge_type]
                self._reverse_edges[target_id] = [e for e in self._reverse_edges[target_id] if e.source_id != source_id or e.edge_type != edge_type]
                self._stats["edges"] -= 1
                self._stats["edge_types"][edge_type.value] -= 1
                removed = True
        else:
            edges_to_remove = [e for e in self._edges.get(source_id, []) if e.target_id == target_id]
            for edge in edges_to_remove:
                self._edge_index.pop((source_id, target_id, edge.edge_type.value), None)
                self._stats["edges"] -= 1
                self._stats["edge_types"][edge.edge_type.value] -= 1
                self._reverse_edges[target_id] = [e for e in self._reverse_edges[target_id] if e.source_id != source_id or e.edge_type != edge.edge_type]
                removed = True
            self._edges[source_id] = [e for e in self._edges[source_id] if e.target_id != target_id]
        return removed

    def get_neighbors(
        self,
        record_id: str,
        edge_types: list[EdgeType] | None = None,
        max_depth: int = 1,
    ) -> list[tuple[str, float, EdgeType]]:
        """Get neighboring nodes with their edge weights and types."""
        if record_id not in self._nodes:
            return []

        results: list[tuple[str, float, EdgeType]] = []
        visited: set[str] = {record_id}
        queue: deque[tuple[str, int, float]] = deque([(record_id, 0, 1.0)])

        while queue:
            current, depth, cumulative_weight = queue.popleft()
            if depth >= max_depth:
                continue

            for edge in self._edges.get(current, []):
                if edge_types and edge.edge_type not in edge_types:
                    continue
                if edge.target_id in visited:
                    continue
                visited.add(edge.target_id)
                weight = cumulative_weight * edge.weight
                results.append((edge.target_id, weight, edge.edge_type))
                if depth + 1 < max_depth:
                    queue.append((edge.target_id, depth + 1, weight))

        return sorted(results, key=lambda x: x[1], reverse=True)

    def get_related(
        self,
        record_id: str,
        edge_types: list[EdgeType] | None = None,
        min_weight: float = 0.0,
        max_results: int = 20,
    ) -> list[tuple[str, float, EdgeType]]:
        """Get related memories with weights above a threshold."""
        neighbors = self.get_neighbors(record_id, edge_types, max_depth=2)
        filtered = [(rid, w, et) for rid, w, et in neighbors if w >= min_weight]
        return filtered[:max_results]

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> list[str] | None:
        """Find a path between two nodes using BFS."""
        if source_id not in self._nodes or target_id not in self._nodes:
            return None
        if source_id == target_id:
            return [source_id]

        visited: set[str] = {source_id}
        queue: deque[tuple[str, list[str]]] = deque([(source_id, [source_id])])

        while queue:
            current, path = queue.popleft()
            if len(path) > max_depth:
                continue

            for edge in self._edges.get(current, []):
                if edge.target_id in visited:
                    continue
                if edge.target_id == target_id:
                    return path + [target_id]
                visited.add(edge.target_id)
                queue.append((edge.target_id, path + [edge.target_id]))

        return None

    def get_strongly_connected_components(self) -> list[list[str]]:
        """Find strongly connected components using Tarjan's algorithm."""
        index_counter = [0]
        stack: list[str] = []
        lowlinks: dict[str, int] = {}
        index: dict[str, int] = {}
        on_stack: set[str] = set()
        result: list[list[str]] = []

        def strongconnect(node: str):
            index[node] = index_counter[0]
            lowlinks[node] = index_counter[0]
            index_counter[0] += 1
            stack.append(node)
            on_stack.add(node)

            for edge in self._edges.get(node, []):
                neighbor = edge.target_id
                if neighbor not in index:
                    strongconnect(neighbor)
                    lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
                elif neighbor in on_stack:
                    lowlinks[node] = min(lowlinks[node], index[neighbor])

            if lowlinks[node] == index[node]:
                component: list[str] = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    component.append(w)
                    if w == node:
                        break
                result.append(component)

        for node in self._nodes:
            if node not in index:
                strongconnect(node)

        return result

    def get_central_nodes(self, top_n: int = 10) -> list[tuple[str, float]]:
        """Get the most central nodes by edge weight sum."""
        centrality: dict[str, float] = defaultdict(float)
        for node in self._nodes:
            for edge in self._edges.get(node, []):
                centrality[node] += edge.weight
                centrality[edge.target_id] += edge.weight

        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        return sorted_nodes[:top_n]

    def get_stats(self) -> dict[str, Any]:
        """Get graph statistics."""
        return {
            "nodes": len(self._nodes),
            "edges": self._stats["edges"],
            "edge_types": dict(self._stats["edge_types"]),
            "avg_degree": self._stats["edges"] / max(len(self._nodes), 1),
        }

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "nodes": len(self._nodes),
            "edges": self._stats["edges"],
        }

    def clear(self) -> None:
        """Clear all nodes and edges."""
        self._nodes.clear()
        self._edges.clear()
        self._reverse_edges.clear()
        self._edge_index.clear()
        self._stats = {
            "nodes": 0,
            "edges": 0,
            "edge_types": defaultdict(int),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize graph to dictionary for persistence."""
        return {
            "nodes": list(self._nodes),
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "edge_type": e.edge_type.value,
                    "weight": e.weight,
                    "created_at": e.created_at,
                    "metadata": e.metadata,
                }
                for edges in self._edges.values()
                for e in edges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryGraph:
        """Deserialize graph from dictionary."""
        graph = cls()
        for node_id in data.get("nodes", []):
            graph.add_node(node_id)
        for edge_data in data.get("edges", []):
            graph.add_edge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                edge_type=EdgeType(edge_data["edge_type"]),
                weight=edge_data.get("weight", 1.0),
                metadata=edge_data.get("metadata", {}),
            )
        return graph


def create_memory_graph() -> MemoryGraph:
    """Factory for creating a memory graph."""
    return MemoryGraph()
