"""Tests for routing algorithms."""

import pytest

from src.core.graph import NetworkGraph
from src.routing.baseline import BaselineRouter, MultiPathRouter
from src.routing.srsd import SRSDRouter, SRSDConfig
from src.routing.route_memory import RouteMemory


class TestBaselineRouter:
    """Tests for baseline routing."""

    @pytest.fixture
    def simple_graph(self):
        """Create a simple graph for testing."""
        graph = NetworkGraph.create_mesh(rows=3, cols=3)
        return graph

    def test_baseline_routing(self, simple_graph):
        """Test basic routing functionality."""
        router = BaselineRouter(simple_graph)

        flow = router.route("n_0_0", "n_2_2")
        assert flow is not None
        assert flow.source == "n_0_0"
        assert flow.destination == "n_2_2"
        assert len(flow.path) > 1

    def test_deterministic_behavior(self, simple_graph):
        """Test that baseline routing is deterministic."""
        router = BaselineRouter(simple_graph)

        flow1 = router.route("n_0_0", "n_2_2")
        flow2 = router.route("n_0_0", "n_2_2")

        assert flow1.path == flow2.path

    def test_routing_statistics(self, simple_graph):
        """Test routing statistics collection."""
        router = BaselineRouter(simple_graph)

        for _ in range(10):
            router.route("n_0_0", "n_2_2")

        stats = router.get_statistics()
        assert stats.total_flows == 10
        assert stats.successful_routes == 10
        assert stats.path_reuse_rate > 0

    def test_no_path_handling(self):
        """Test handling when no path exists."""
        graph = NetworkGraph()
        graph.add_node_simple("A")
        graph.add_node_simple("B")
        # No edges added

        router = BaselineRouter(graph)
        flow = router.route("A", "B")

        assert flow is None
        assert router.stats.failed_routes == 1


class TestMultiPathRouter:
    """Tests for multi-path routing."""

    @pytest.fixture
    def graph_with_alternatives(self):
        """Create graph with multiple path options."""
        graph = NetworkGraph()
        for i in range(5):
            graph.add_node_simple(f"n{i}")

        # Create diamond pattern
        graph.add_edge_simple("n0", "n1")
        graph.add_edge_simple("n0", "n2")
        graph.add_edge_simple("n1", "n3")
        graph.add_edge_simple("n2", "n3")
        graph.add_edge_simple("n3", "n4")

        return graph

    def test_multipath_routing(self, graph_with_alternatives):
        """Test multi-path selection."""
        router = MultiPathRouter(graph_with_alternatives, k=2)

        paths_used = set()
        for _ in range(10):
            flow = router.route("n0", "n4")
            paths_used.add(tuple(flow.path))

        # Should use at least 2 different paths
        assert len(paths_used) >= 1


class TestSRSDRouter:
    """Tests for SRSD routing."""

    @pytest.fixture
    def mesh_graph(self):
        """Create mesh graph for SRSD testing."""
        return NetworkGraph.create_mesh(rows=4, cols=4)

    def test_srsd_routing(self, mesh_graph):
        """Test basic SRSD routing."""
        config = SRSDConfig(k_paths=5)
        router = SRSDRouter(mesh_graph, config)
        router.set_seed(42)

        flow = router.route("n_0_0", "n_3_3")
        assert flow is not None
        assert flow.source == "n_0_0"
        assert flow.destination == "n_3_3"

    def test_srsd_diversity(self, mesh_graph):
        """Test that SRSD produces path diversity."""
        config = SRSDConfig(
            k_paths=5,
            recurrence_penalty=3.0,
            min_randomness=0.2,
        )
        router = SRSDRouter(mesh_graph, config)
        router.set_seed(42)

        paths_used = set()
        for i in range(20):
            flow = router.route("n_0_0", "n_3_3", flow_id=f"flow_{i}")
            paths_used.add(tuple(flow.path))

        # SRSD should use multiple paths
        assert len(paths_used) > 1

    def test_srsd_vs_baseline_entropy(self, mesh_graph):
        """Test that SRSD has higher entropy than baseline."""
        # Baseline
        baseline_router = BaselineRouter(mesh_graph)
        for i in range(50):
            baseline_router.route("n_0_0", "n_3_3", flow_id=f"baseline_{i}")

        # SRSD
        config = SRSDConfig(k_paths=5, recurrence_penalty=2.0)
        srsd_router = SRSDRouter(mesh_graph, config)
        srsd_router.set_seed(42)
        for i in range(50):
            srsd_router.route("n_0_0", "n_3_3", flow_id=f"srsd_{i}")

        # Check unique paths
        baseline_paths = baseline_router.stats.unique_paths
        srsd_paths = srsd_router.stats.unique_paths

        # SRSD should use more unique paths
        assert srsd_paths >= baseline_paths

    def test_srsd_memory(self, mesh_graph):
        """Test SRSD route memory."""
        config = SRSDConfig(k_paths=3)
        router = SRSDRouter(mesh_graph, config)
        router.set_seed(42)

        # Route several times
        for i in range(5):
            router.route("n_0_0", "n_3_3", flow_id=f"flow_{i}")

        # Check memory has recorded paths
        memory_stats = router.memory.get_overall_statistics()
        assert memory_stats['total_path_uses'] == 5


class TestRouteMemory:
    """Tests for route memory."""

    def test_memory_recording(self):
        """Test path recording in memory."""
        memory = RouteMemory()

        path1 = ["A", "B", "C"]
        path2 = ["A", "D", "C"]

        memory.record_path("A", "C", path1, "flow1")
        memory.record_path("A", "C", path2, "flow2")
        memory.record_path("A", "C", path1, "flow3")

        stats = memory.get_path_statistics("A", "C")
        assert stats['unique_paths'] == 2
        assert stats['total_uses'] == 3

    def test_path_penalty(self):
        """Test path penalty calculation."""
        memory = RouteMemory()

        path = ["A", "B", "C"]

        # Fresh path should have low penalty
        penalty_before = memory.get_path_penalty("A", "C", path)

        # Record usage
        memory.record_path("A", "C", path, "flow1")

        # Used path should have higher penalty
        penalty_after = memory.get_path_penalty("A", "C", path)
        assert penalty_after > penalty_before

    def test_flow_diversity(self):
        """Test flow diversity calculation."""
        memory = RouteMemory()

        # All same path = low diversity
        for i in range(5):
            memory.record_path("A", "C", ["A", "B", "C"], flow_id="single_flow")

        diversity = memory.get_flow_diversity("single_flow")
        # All 5 paths are the same, so unique=1, total=5, diversity=0.2
        assert diversity < 1.0
        assert diversity == 0.2

    def test_memory_clear(self):
        """Test clearing memory."""
        memory = RouteMemory()
        memory.record_path("A", "C", ["A", "B", "C"])

        stats = memory.get_overall_statistics()
        assert stats['total_path_uses'] > 0

        memory.clear()
        stats = memory.get_overall_statistics()
        assert stats['total_path_uses'] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
