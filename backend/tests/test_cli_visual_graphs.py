"""Tests for CLI Visual Engine - Graphs/Flowcharts."""

import pytest
from backend.cli.visual.graphs import (
    GraphRenderer,
    Node,
    Edge,
    NodeType,
    EdgeType,
    render_schema,
    create_memory_schema,
    create_egress_schema,
    create_pipeline_schema,
    create_browser_schema,
    create_project_memory_schema,
    SCHEMAS,
)


class TestNode:
    """Test Node dataclass."""
    
    def test_node_creation(self):
        """Test creating a node."""
        node = Node(id="test", label="Test Node", type=NodeType.PROCESS)
        assert node.id == "test"
        assert node.label == "Test Node"
        assert node.type == NodeType.PROCESS
    
    def test_node_default_label(self):
        """Test node label defaults to id."""
        node = Node(id="test", label="", type=NodeType.PROCESS)
        assert node.label == "test"
    
    def test_node_empty_id_raises(self):
        """Test empty node id raises ValueError."""
        with pytest.raises(ValueError):
            Node(id="", label="Test", type=NodeType.PROCESS)


class TestEdge:
    """Test Edge dataclass."""
    
    def test_edge_creation(self):
        """Test creating an edge."""
        edge = Edge(from_id="a", to_id="b", type=EdgeType.FLOW)
        assert edge.from_id == "a"
        assert edge.to_id == "b"
        assert edge.type == EdgeType.FLOW


class TestGraphRenderer:
    """Test GraphRenderer class."""
    
    def test_add_node(self):
        """Test adding nodes."""
        g = GraphRenderer()
        g.add_node(Node("a", "Node A"))
        g.add_node(Node("b", "Node B"))
        assert len(g.nodes) == 2
    
    def test_add_edge(self):
        """Test adding edges."""
        g = GraphRenderer()
        g.add_node(Node("a", "Node A"))
        g.add_node(Node("b", "Node B"))
        g.add_edge(Edge("a", "b"))
        assert len(g.edges) == 1
    
    def test_add_edge_invalid_nodes(self):
        """Test adding edge with invalid nodes raises."""
        g = GraphRenderer()
        g.add_node(Node("a", "Node A"))
        with pytest.raises(ValueError):
            g.add_edge(Edge("a", "nonexistent"))
    
    def test_render_simple(self):
        """Test rendering a simple graph."""
        g = GraphRenderer()
        g.node("start", "Start", NodeType.START_END)
        g.node("process", "Process", NodeType.PROCESS)
        g.node("end", "End", NodeType.START_END)
        g.edge("start", "process")
        g.edge("process", "end")
        
        output = g.render()
        assert "Start" in output
        assert "Process" in output
        assert "End" in output
    
    def test_to_graph_easy(self):
        """Test Graph-Easy export."""
        g = GraphRenderer()
        g.node("a", "Node A")
        g.node("b", "Node B")
        g.edge("a", "b")
        
        ge_output = g.to_graph_easy()
        assert "graph {" in ge_output
        assert "Node A" in ge_output
        assert "a -> b" in ge_output


class TestPredefinedSchemas:
    """Test pre-defined schema functions."""
    
    def test_create_memory_schema(self):
        """Test memory schema creation."""
        g = create_memory_schema()
        assert "user" in g.nodes
        assert "recall" in g.nodes
        assert "llm" in g.nodes
        assert len(g.edges) > 0
    
    def test_create_egress_schema(self):
        """Test egress schema creation."""
        g = create_egress_schema()
        assert "request" in g.nodes
        assert "policy" in g.nodes
        assert "allow" in g.nodes
        assert len(g.edges) > 0
    
    def test_create_pipeline_schema(self):
        """Test pipeline schema creation."""
        g = create_pipeline_schema()
        assert "request" in g.nodes
        assert "inlet" in g.nodes
        assert "llm" in g.nodes
        assert "outlet" in g.nodes
    
    def test_create_browser_schema(self):
        """Test browser schema creation."""
        g = create_browser_schema()
        assert "task" in g.nodes
        assert "execute" in g.nodes
    
    def test_create_project_memory_schema(self):
        """Test project memory schema creation."""
        g = create_project_memory_schema()
        assert "fact" in g.nodes
        assert "store" in g.nodes


class TestRenderSchema:
    """Test render_schema function."""
    
    def test_render_memory_schema(self):
        """Test rendering memory schema."""
        output = render_schema("memory")
        assert "User Query" in output
        assert "Recall from Spine" in output
    
    def test_render_egress_schema(self):
        """Test rendering egress schema."""
        output = render_schema("egress")
        assert "Outbound Request" in output
        assert "Check Policy" in output
    
    def test_render_pipeline_schema(self):
        """Test rendering pipeline schema."""
        output = render_schema("pipeline")
        assert "Incoming Request" in output
        assert "Inlet Filters" in output
    
    def test_render_browser_schema(self):
        """Test rendering browser schema."""
        output = render_schema("browser")
        assert "Browser Task" in output
        assert "List Tools" in output
    
    def test_render_project_schema(self):
        """Test rendering project schema."""
        output = render_schema("project")
        assert "New Fact" in output
        assert "Active Project" in output
    
    def test_render_unknown_schema(self):
        """Test rendering unknown schema."""
        output = render_schema("unknown")
        assert "Unknown schema" in output
    
    def test_render_graph_easy_format(self):
        """Test rendering in Graph-Easy format."""
        output = render_schema("memory", as_graph_easy=True)
        assert "graph {" in output
        assert "layout:" in output


class TestSchemasDict:
    """Test SCHEMAS dictionary."""
    
    def test_schemas_contains_expected(self):
        """Test SCHEMAS contains all expected schemas."""
        expected = {"memory", "egress", "pipeline", "browser", "project"}
        assert set(SCHEMAS.keys()) == expected
    
    def test_schema_functions_callable(self):
        """Test all schema functions are callable."""
        for name, func in SCHEMAS.items():
            g = func()
            assert isinstance(g, GraphRenderer)