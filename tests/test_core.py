"""Tests for core network modeling components."""

import pytest
import time

from src.core.edge import Edge, EdgeAttributes
from src.core.node import Node, NodeType, NodeState
from src.core.graph import NetworkGraph


class TestEdge:
    """Tests for Edge class."""

    def test_edge_creation(self):
        """Test basic edge creation."""
        edge = Edge(source="A", target="B")
        assert edge.source == "A"
        assert edge.target == "B"
        assert edge.id == "A->B"
        assert edge.usage_count == 0

    def test_edge_with_attributes(self):
        """Test edge with custom attributes."""
        attrs = EdgeAttributes(
            weight=2.0,
            latency=10.0,
            recurrence=0.5,
            exposure=0.3,
        )
        edge = Edge(source="A", target="B", attributes=attrs)
        assert edge.attributes.weight == 2.0
        assert edge.attributes.latency == 10.0

    def test_edge_usage_recording(self):
        """Test recording edge usage."""
        edge = Edge(source="A", target="B")
        edge.record_usage()
        assert edge.usage_count == 1
        assert edge.last_used is not None

        edge.record_usage()
        assert edge.usage_count == 2

    def test_effective_weight(self):
        """Test effective weight calculation with penalties."""
        attrs = EdgeAttributes(weight=1.0, recurrence=0.5, exposure=0.3)
        edge = Edge(source="A", target="B", attributes=attrs)

        # Without penalties
        base_weight = edge.get_effective_weight(
            recurrence_penalty=0, exposure_penalty=0
        )
        assert base_weight == 1.0

        # With penalties
        penalized_weight = edge.get_effective_weight(
            recurrence_penalty=1.0, exposure_penalty=1.0
        )
        assert penalized_weight > base_weight

    def test_edge_serialization(self):
        """Test edge serialization and deserialization."""
        attrs = EdgeAttributes(weight=2.0, latency=5.0)
        edge = Edge(source="A", target="B", attributes=attrs)
        edge.record_usage()

        data = edge.to_dict()
        restored = Edge.from_dict(data)

        assert restored.source == edge.source
        assert restored.target == edge.target
        assert restored.attributes.weight == edge.attributes.weight


class TestNode:
    """Tests for Node class."""

    def test_node_creation(self):
        """Test basic node creation."""
        node = Node(id="node1")
        assert node.id == "node1"
        assert node.node_type == NodeType.ROUTER
        assert node.state == NodeState.ACTIVE

    def test_node_is_active(self):
        """Test node activity status."""
        node = Node(id="node1")
        assert node.is_active()

        node.state = NodeState.FAILED
        assert not node.is_active()

    def test_node_edge_management(self):
        """Test adding and removing edges."""
        node = Node(id="node1")

        node.add_outgoing_edge("node1->node2")
        assert "node1->node2" in node.outgoing_edges

        node.add_incoming_edge("node0->node1")
        assert "node0->node1" in node.incoming_edges

        node.remove_outgoing_edge("node1->node2")
        assert "node1->node2" not in node.outgoing_edges

    def test_node_neighbors(self):
        """Test getting neighbors from outgoing edges."""
        node = Node(id="node1")
        node.add_outgoing_edge("node1->node2")
        node.add_outgoing_edge("node1->node3")

        neighbors = node.get_neighbors()
        assert "node2" in neighbors
        assert "node3" in neighbors

    def test_node_forward_packet(self):
        """Test packet forwarding recording."""
        node = Node(id="node1")
        node.forward_packet("flow1", packet_size=100)

        assert node.stats.packets_forwarded == 1
        assert node.stats.bytes_forwarded == 100
        assert "flow1" in node.stats.flows_seen

    def test_qkd_node(self):
        """Test QKD-enabled node."""
        node = Node(id="qkd1", node_type=NodeType.QKD_ENABLED)
        node.qkd_key_pool = 1000
        node.qkd_generation_rate = 100

        assert node.is_qkd_capable()

        # Test key consumption
        assert node.consume_qkd_keys(500)
        assert node.qkd_key_pool == 500
        assert not node.consume_qkd_keys(1000)  # Not enough keys


class TestNetworkGraph:
    """Tests for NetworkGraph class."""

    def test_graph_creation(self):
        """Test basic graph creation."""
        graph = NetworkGraph(name="test")
        assert graph.name == "test"
        assert graph.num_nodes == 0
        assert graph.num_edges == 0

    def test_add_nodes(self):
        """Test adding nodes to graph."""
        graph = NetworkGraph()
        graph.add_node_simple("A")
        graph.add_node_simple("B")

        assert graph.num_nodes == 2
        assert graph.get_node("A") is not None
        assert graph.get_node("B") is not None

    def test_add_edges(self):
        """Test adding edges to graph."""
        graph = NetworkGraph()
        graph.add_node_simple("A")
        graph.add_node_simple("B")
        graph.add_edge_simple("A", "B")

        assert graph.num_edges == 1
        assert graph.get_edge_between("A", "B") is not None

    def test_bidirectional_edges(self):
        """Test adding bidirectional edges."""
        graph = NetworkGraph()
        graph.add_node_simple("A")
        graph.add_node_simple("B")
        graph.add_edge_simple("A", "B", bidirectional=True)

        assert graph.num_edges == 2
        assert graph.get_edge_between("A", "B") is not None
        assert graph.get_edge_between("B", "A") is not None

    def test_shortest_path(self):
        """Test shortest path finding."""
        graph = NetworkGraph()
        for i in range(4):
            graph.add_node_simple(f"n{i}")

        graph.add_edge_simple("n0", "n1")
        graph.add_edge_simple("n1", "n2")
        graph.add_edge_simple("n2", "n3")
        graph.add_edge_simple("n0", "n3", weight=10.0)  # Longer path

        path = graph.shortest_path("n0", "n3")
        assert path == ["n0", "n1", "n2", "n3"]

    def test_k_shortest_paths(self):
        """Test finding k shortest paths."""
        graph = NetworkGraph()
        for i in range(4):
            graph.add_node_simple(f"n{i}")

        graph.add_edge_simple("n0", "n1")
        graph.add_edge_simple("n1", "n3")
        graph.add_edge_simple("n0", "n2")
        graph.add_edge_simple("n2", "n3")

        paths = graph.k_shortest_paths("n0", "n3", k=2)
        assert len(paths) == 2

    def test_mesh_topology(self):
        """Test creating mesh topology."""
        graph = NetworkGraph.create_mesh(rows=3, cols=3)

        assert graph.num_nodes == 9
        # Each internal node has 4 edges (bidirectional to neighbors)
        # This is a 3x3 mesh

    def test_barabasi_albert(self):
        """Test creating Barabasi-Albert topology."""
        graph = NetworkGraph.create_barabasi_albert(n=20, m=2, seed=42)

        assert graph.num_nodes == 20
        assert graph.num_edges > 0

    def test_watts_strogatz(self):
        """Test creating Watts-Strogatz topology."""
        graph = NetworkGraph.create_watts_strogatz(n=20, k=4, p=0.1, seed=42)

        assert graph.num_nodes == 20
        assert graph.num_edges > 0

    def test_graph_serialization(self):
        """Test graph serialization and deserialization."""
        graph = NetworkGraph.create_mesh(rows=2, cols=2)

        data = graph.to_dict()
        restored = NetworkGraph.from_dict(data)

        assert restored.num_nodes == graph.num_nodes
        assert restored.num_edges == graph.num_edges

    def test_path_length(self):
        """Test path length calculation."""
        graph = NetworkGraph()
        graph.add_node_simple("A")
        graph.add_node_simple("B")
        graph.add_node_simple("C")
        graph.add_edge_simple("A", "B", weight=2.0)
        graph.add_edge_simple("B", "C", weight=3.0)

        path = ["A", "B", "C"]
        length = graph.path_length(path)
        assert length == 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
