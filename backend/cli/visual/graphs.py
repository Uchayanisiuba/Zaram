"""Graph-Easy style ASCII flowchart rendering."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
from collections import defaultdict


class NodeType(Enum):
    """Types of nodes in the flowchart."""
    PROCESS = "box"           # Rectangle - process/operation
    DECISION = "diamond"      # Diamond - decision point
    START_END = "ellipse"     # Ellipse - start/end
    IO = "parallelogram"      # Parallelogram - input/output
    DATABASE = "cylinder"     # Cylinder - data store
    SUBROUTINE = "hexagon"    # Hexagon - subroutine


class EdgeType(Enum):
    """Types of edges in the flowchart."""
    FLOW = "->"       # Normal flow
    ASYNC = "-.->"    # Async flow
    EGRESS = "==>"    # Egress (data leaving)
    CONDITIONAL = "-->" # Conditional
    RETURN = "=>>"    # Return


@dataclass
class Node:
    """A node in the flowchart."""
    id: str
    label: str
    type: NodeType = NodeType.PROCESS
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id:
            raise ValueError("Node must have an id")
        if not self.label:
            self.label = self.id


@dataclass
class Edge:
    """An edge connecting two nodes."""
    from_id: str
    to_id: str
    type: EdgeType = EdgeType.FLOW
    label: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


class GraphRenderer:
    """Renders Graph-Easy style ASCII flowcharts."""
    
    NODE_SHAPES = {
        NodeType.PROCESS: ("[", "]"),
        NodeType.DECISION: ("{", "}"),
        NodeType.START_END: ("(", ")"),
        NodeType.IO: (">", "<"),
        NodeType.DATABASE: ("(", ")"),
        NodeType.SUBROUTINE: ("<", ">"),
    }
    
    EDGE_CHARS = {
        EdgeType.FLOW: "->",
        EdgeType.ASYNC: "-.->",
        EdgeType.EGRESS: "==>",
        EdgeType.CONDITIONAL: "-->",
        EdgeType.RETURN: "=>>",
    }
    
    def __init__(self, layout: str = "lr"):
        """
        Initialize renderer.
        
        Args:
            layout: "lr" for left-to-right, "tb" for top-to-bottom
        """
        self.layout = layout
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._node_order: List[str] = []
    
    def add_node(self, node: Node) -> "GraphRenderer":
        """Add a node to the graph."""
        self.nodes[node.id] = node
        if node.id not in self._node_order:
            self._node_order.append(node.id)
        return self
    
    def add_edge(self, edge: Edge) -> "GraphRenderer":
        """Add an edge to the graph."""
        if edge.from_id not in self.nodes:
            raise ValueError(f"Source node {edge.from_id} not found")
        if edge.to_id not in self.nodes:
            raise ValueError(f"Target node {edge.to_id} not found")
        self.edges.append(edge)
        return self
    
    def node(self, id: str, label: str, type: NodeType = NodeType.PROCESS, **metadata) -> "GraphRenderer":
        """Convenience method to add a node."""
        return self.add_node(Node(id=id, label=label, type=type, metadata=metadata))
    
    def edge(self, from_id: str, to_id: str, type: EdgeType = EdgeType.FLOW, label: Optional[str] = None, **metadata) -> "GraphRenderer":
        """Convenience method to add an edge."""
        return self.add_edge(Edge(from_id=from_id, to_id=to_id, type=type, label=label, metadata=metadata))
    
    def _render_node(self, node: Node) -> str:
        """Render a single node."""
        open_char, close_char = self.NODE_SHAPES.get(node.type, ("[", "]"))
        label = node.label
        # Escape brackets in label
        label = label.replace("[", "\\[").replace("]", "\\]")
        return f"{open_char} {label} {close_char}"
    
    def _render_edge(self, edge: Edge) -> str:
        """Render a single edge."""
        edge_char = self.EDGE_CHARS.get(edge.type, "->")
        if edge.label:
            return f"{edge.from_id} {edge_char} {edge.label} {edge.to_id}"
        return f"{edge.from_id} {edge_char} {edge.to_id}"
    
    def _build_grid(self) -> List[List[str]]:
        """Build a grid representation for layout."""
        # Simple topological layout
        # Group nodes by their "layer" (distance from start nodes)
        in_degree = defaultdict(int)
        out_edges = defaultdict(list)
        
        for edge in self.edges:
            out_edges[edge.from_id].append(edge.to_id)
            in_degree[edge.to_id] += 1
        
        # Find start nodes (in_degree == 0)
        start_nodes = [nid for nid in self._node_order if in_degree[nid] == 0]
        if not start_nodes:
            start_nodes = self._node_order[:1]
        
        # Assign layers using BFS
        layers = {}
        queue = [(nid, 0) for nid in start_nodes]
        visited = set()
        
        while queue:
            nid, layer = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            layers[nid] = layer
            for target in out_edges[nid]:
                if target not in visited:
                    queue.append((target, layer + 1))
        
        # Handle any disconnected nodes
        for nid in self._node_order:
            if nid not in layers:
                layers[nid] = len(layers)
        
        # Group by layer
        layer_nodes = defaultdict(list)
        for nid, layer in layers.items():
            layer_nodes[layer].append(nid)
        
        # Build grid
        max_layer = max(layers.values()) if layers else 0
        grid = []
        
        for layer in range(max_layer + 1):
            nodes_in_layer = layer_nodes.get(layer, [])
            row = []
            for nid in nodes_in_layer:
                row.append(self._render_node(self.nodes[nid]))
            if row:
                grid.append(row)
        
        return grid
    
    def render(self) -> str:
        """Render the flowchart as ASCII art."""
        if not self.nodes:
            return "Empty graph"
        
        if self.layout == "tb":
            return self._render_top_bottom()
        else:
            return self._render_left_right()
    
    def _render_left_right(self) -> str:
        """Render left-to-right layout."""
        lines = []
        grid = self._build_grid()
        
        # Calculate column widths
        col_widths = []
        for row in grid:
            for i, cell in enumerate(row):
                if i >= len(col_widths):
                    col_widths.append(len(cell))
                else:
                    col_widths[i] = max(col_widths[i], len(cell))
        
        # Render each row
        for row_idx, row in enumerate(grid):
            line_parts = []
            for col_idx, cell in enumerate(row):
                line_parts.append(cell.ljust(col_widths[col_idx]))
            
            lines.append("   ".join(line_parts))
            
            # Add edges between this row and next
            if row_idx < len(grid) - 1:
                edge_line = []
                for col_idx, cell in enumerate(row):
                    node_id = None
                    for nid, node in self.nodes.items():
                        if self._render_node(node) == cell.strip():
                            node_id = nid
                            break
                    
                    if node_id:
                        # Find edges from this node to next layer
                        next_layer_nodes = grid[row_idx + 1]
                        for next_cell in next_layer_nodes:
                            next_nid = None
                            for nid2, node2 in self.nodes.items():
                                if self._render_node(node2) == next_cell.strip():
                                    next_nid = nid2
                                    break
                            
                            if next_nid:
                                for edge in self.edges:
                                    if edge.from_id == node_id and edge.to_id == next_nid:
                                        edge_char = self.EDGE_CHARS.get(edge.type, "->")
                                        label_part = f" {edge.label} " if edge.label else " "
                                        edge_line.append(f"{label_part}{edge_char}")
                                        break
                                else:
                                    edge_line.append(" " * (col_widths[col_idx] if col_idx < len(col_widths) else 10))
                            else:
                                edge_line.append(" " * (col_widths[col_idx] if col_idx < len(col_widths) else 10))
                        else:
                            edge_line.append(" " * (col_widths[col_idx] if col_idx < len(col_widths) else 10))
                    else:
                        edge_line.append(" " * (col_widths[col_idx] if col_idx < len(col_widths) else 10))
                
                if any(e.strip() for e in edge_line):
                    lines.append("   ".join(edge_line))
        
        return "\n".join(lines)
    
    def _render_top_bottom(self) -> str:
        """Render top-to-bottom layout."""
        # Simple vertical layout - each node on its own line with edges
        lines = []
        rendered_nodes = set()
        
        # Find start nodes
        in_degree = defaultdict(int)
        for edge in self.edges:
            in_degree[edge.to_id] += 1
        
        start_nodes = [nid for nid in self._node_order if in_degree[nid] == 0]
        if not start_nodes:
            start_nodes = self._node_order[:1]
        
        def render_node_tree(nid: str, prefix: str = "", is_last: bool = True, visited: Optional[Set[str]] = None):
            if visited is None:
                visited = set()
            if nid in visited:
                return
            visited.add(nid)
            
            node = self.nodes[nid]
            connector = "+-- " if is_last else "+-- "
            lines.append(f"{prefix}{connector}{self._render_node(node)}")
            
            # Find outgoing edges
            outgoing = [e for e in self.edges if e.from_id == nid]
            for i, edge in enumerate(outgoing):
                edge_char = self.EDGE_CHARS.get(edge.type, "->")
                label = f" [{edge.label}]" if edge.label else ""
                edge_prefix = prefix + ("    " if is_last else "|   ")
                lines.append(f"{edge_prefix}{edge_char}{label}")
                render_node_tree(edge.to_id, edge_prefix, i == len(outgoing) - 1, visited)
        
        for i, start in enumerate(start_nodes):
            render_node_tree(start, "", i == len(start_nodes) - 1)
        
        return "\n".join(lines)
    
    def to_graph_easy(self) -> str:
        """Export as Graph-Easy format for external rendering."""
        lines = ["graph {"]
        lines.append(f"  layout: {self.layout};")
        lines.append("")
        
        for node in self.nodes.values():
            shape = node.type.value
            lines.append(f'  {node.id} [label="{node.label}", shape={shape}];')
        
        lines.append("")
        
        for edge in self.edges:
            edge_type = edge.type.value
            label = f' [label="{edge.label}"]' if edge.label else ""
            lines.append(f'  {edge.from_id} {edge_type} {edge.to_id}{label};')
        
        lines.append("}")
        return "\n".join(lines)


# Pre-defined graph schemas
def create_memory_schema() -> GraphRenderer:
    """Create the Spine memory architecture flowchart."""
    g = GraphRenderer(layout="tb")
    
    g.node("user", "User Query", NodeType.START_END)
    g.node("recall", "Recall from Spine", NodeType.PROCESS)
    g.node("rank", "Rank by Relevance", NodeType.PROCESS)
    g.node("inject", "Inject Context", NodeType.PROCESS)
    g.node("llm", "LLM Generation", NodeType.PROCESS)
    g.node("validate", "Validate Citations", NodeType.PROCESS)
    g.node("egress", "Egress Gate", NodeType.DECISION)
    g.node("response", "Response to User", NodeType.START_END)
    g.node("log", "Egress Log", NodeType.DATABASE)
    
    g.edge("user", "recall")
    g.edge("recall", "rank")
    g.edge("rank", "inject")
    g.edge("inject", "llm")
    g.edge("llm", "validate")
    g.edge("validate", "egress", EdgeType.CONDITIONAL, "has egress")
    g.edge("egress", "response", label="allowed")
    g.edge("egress", "log", EdgeType.EGRESS, label="blocked/logged")
    g.edge("egress", "log", EdgeType.EGRESS, label="logged")
    
    return g


def create_egress_schema() -> GraphRenderer:
    """Create the egress pipeline flowchart."""
    g = GraphRenderer(layout="lr")
    
    g.node("request", "Outbound Request", NodeType.START_END)
    g.node("classify", "Classify Destination", NodeType.PROCESS)
    g.node("policy", "Check Policy", NodeType.DECISION)
    g.node("ask", "Ask User", NodeType.IO)
    g.node("deny", "Deny Request", NodeType.PROCESS)
    g.node("log_deny", "Log Denial", NodeType.DATABASE)
    g.node("allow", "Allow Request", NodeType.PROCESS)
    g.node("send", "Send Request", NodeType.PROCESS)
    g.node("log_allow", "Log Allowance", NodeType.DATABASE)
    g.node("response", "Response", NodeType.START_END)
    
    g.edge("request", "classify")
    g.edge("classify", "policy")
    g.edge("policy", "deny", label="DENY")
    g.edge("deny", "log_deny", EdgeType.EGRESS)
    g.edge("policy", "ask", label="ASK")
    g.edge("ask", "allow", label="yes")
    g.edge("ask", "deny", label="no")
    g.edge("policy", "allow", label="ALLOW")
    g.edge("allow", "send")
    g.edge("send", "log_allow", EdgeType.EGRESS)
    g.edge("send", "response")
    
    return g


def create_pipeline_schema() -> GraphRenderer:
    """Create the pipeline architecture flowchart."""
    g = GraphRenderer(layout="tb")
    
    g.node("request", "Incoming Request", NodeType.START_END)
    g.node("inlet", "Inlet Filters", NodeType.PROCESS)
    g.node("spine", "Spine Injection", NodeType.PROCESS)
    g.node("budget", "Token Budget", NodeType.PROCESS)
    g.node("normalize", "Param Normalize", NodeType.PROCESS)
    g.node("llm", "LLM Call", NodeType.PROCESS)
    g.node("outlet", "Outlet Filters", NodeType.PROCESS)
    g.node("egress_g", "Egress Guard", NodeType.PROCESS)
    g.node("pii", "PII Scrubber", NodeType.PROCESS)
    g.node("cite", "Citation Validate", NodeType.PROCESS)
    g.node("response", "Final Response", NodeType.START_END)
    
    g.edge("request", "inlet")
    g.edge("inlet", "spine", label="priority=20")
    g.edge("spine", "budget", label="priority=25")
    g.edge("budget", "normalize", label="priority=30")
    g.edge("normalize", "llm")
    g.edge("llm", "outlet")
    g.edge("outlet", "egress_g", label="priority=10")
    g.edge("egress_g", "pii", label="priority=15")
    g.edge("pii", "cite", label="priority=20")
    g.edge("cite", "response")
    
    return g


def create_browser_schema() -> GraphRenderer:
    """Create the browser automation flowchart."""
    g = GraphRenderer(layout="lr")
    
    g.node("task", "Browser Task", NodeType.START_END)
    g.node("list_tools", "List Tools", NodeType.PROCESS)
    g.node("select", "Model Selects Tool", NodeType.DECISION)
    g.node("confirm", "Confirm Action", NodeType.DECISION)
    g.node("execute", "Execute via CDP", NodeType.PROCESS)
    g.node("egress_b", "Egress Check", NodeType.DECISION)
    g.node("result", "Tool Result", NodeType.IO)
    g.node("log", "Egress Log", NodeType.DATABASE)
    g.node("loop", "Continue?", NodeType.DECISION)
    g.node("response", "Final Response", NodeType.START_END)
    
    g.edge("task", "list_tools")
    g.edge("list_tools", "select")
    g.edge("select", "confirm")
    g.edge("confirm", "execute", label="approved")
    g.edge("confirm", "result", type=EdgeType.CONDITIONAL, label="denied")
    g.edge("execute", "egress_b")
    g.edge("egress_b", "result", label="allowed")
    g.edge("egress_b", "log", type=EdgeType.EGRESS, label="denied")
    g.edge("result", "loop")
    g.edge("loop", "select", label="yes")
    g.edge("loop", "response", label="no")
    
    return g


def create_project_memory_schema() -> GraphRenderer:
    """Create project-scoped memory flowchart."""
    g = GraphRenderer(layout="tb")
    
    g.node("fact", "New Fact", NodeType.START_END)
    g.node("scope_check", "Active Project?", NodeType.DECISION)
    g.node("global", "Scope: global", NodeType.PROCESS)
    g.node("project", "Scope: project:<id>", NodeType.PROCESS)
    g.node("store", "Store in Spine", NodeType.DATABASE)
    g.node("recall_q", "Recall Query", NodeType.START_END)
    g.node("recall_scope", "Filter by Scope", NodeType.PROCESS)
    g.node("results", "Scoped Results", NodeType.IO)
    
    g.edge("fact", "scope_check")
    g.edge("scope_check", "global", label="no")
    g.edge("scope_check", "project", label="yes")
    g.edge("global", "store")
    g.edge("project", "store")
    g.edge("recall_q", "recall_scope")
    g.edge("recall_scope", "results")
    
    return g


SCHEMAS = {
    "memory": create_memory_schema,
    "egress": create_egress_schema,
    "pipeline": create_pipeline_schema,
    "browser": create_browser_schema,
    "project": create_project_memory_schema,
}


def render_schema(schema_name: str, as_graph_easy: bool = False) -> str:
    """Render a pre-defined schema by name."""
    schema_name = schema_name.lower()
    if schema_name not in SCHEMAS:
        available = ", ".join(SCHEMAS.keys())
        return f"Unknown schema: {schema_name}. Available: {available}"
    
    graph = SCHEMAS[schema_name]()
    
    if as_graph_easy:
        return graph.to_graph_easy()
    
    return graph.render()