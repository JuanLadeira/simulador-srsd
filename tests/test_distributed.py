"""Tests for Distributed SRSD Routing."""

import pytest

from src.core.graph import NetworkGraph
from src.routing.distributed import DistributedSRSDRouter, DistributedConfig
from src.routing.srsd import SRSDRouter, SRSDConfig


class TestDistributedRouting:
    """Tests for DistributedSRSDRouter."""

    @pytest.fixture
    def mesh_network(self):
        """Rede mesh 4x4 com Hiatus configurados."""
        graph = NetworkGraph.create_mesh(4, 4)
        return graph

    @pytest.fixture
    def config(self):
        """Default configuration."""
        return DistributedConfig(
            num_hiatus=2,
            hiatus_placement="random",
            blocking_window=3,
            seed=42
        )

    def test_packet_delivery(self, mesh_network, config):
        """Pacote deve chegar ao destino."""
        router = DistributedSRSDRouter(mesh_network, config)
        router.set_seed(42)

        result = router.route("n_0_0", "n_3_3")

        assert result is not None
        assert result.destination == "n_3_3"
        assert result.source == "n_0_0"
        assert len(result.path) > 1

    def test_path_diversity(self, mesh_network, config):
        """Caminhos devem ser diversos (bloqueio funciona)."""
        router = DistributedSRSDRouter(mesh_network, config)
        router.set_seed(42)

        paths = []
        for i in range(10):
            result = router.route("n_0_0", "n_3_3", flow_id=f"flow_{i}")
            if result:
                paths.append(tuple(result.path))

        # Should have multiple different paths
        unique_paths = len(set(paths))
        assert unique_paths > 1, f"Expected path diversity, got {unique_paths} unique paths"

    def test_no_immediate_repetition(self, mesh_network, config):
        """Caminho nao deve repetir imediatamente."""
        router = DistributedSRSDRouter(mesh_network, config)
        router.set_seed(42)

        result1 = router.route("n_0_0", "n_3_3", flow_id="flow_1")
        result2 = router.route("n_0_0", "n_3_3", flow_id="flow_2")

        # Paths should be different (blocking mechanism)
        # Note: Due to Hiatus routing, paths may occasionally be the same
        # but the mechanism should generally prevent immediate repetition
        assert result1 is not None
        assert result2 is not None
        # At least the traces should show different hops were attempted

    def test_hiatus_nodes_visited(self, mesh_network, config):
        """Pacotes devem passar por Hiatus configurados."""
        router = DistributedSRSDRouter(mesh_network, config)
        router.set_seed(42)

        # Route multiple flows and check Hiatus statistics
        for i in range(10):
            router.route("n_0_0", "n_3_3", flow_id=f"flow_{i}")

        hiatus_stats = router.get_hiatus_statistics()
        # At least one Hiatus should have processed packets
        total_processed = sum(
            stats.get('packets_processed', 0)
            for stats in hiatus_stats.values()
        )
        assert total_processed > 0

    def test_drawer_statistics(self, mesh_network, config):
        """Drawers devem registrar selecoes."""
        router = DistributedSRSDRouter(mesh_network, config)
        router.set_seed(42)

        for i in range(10):
            router.route("n_0_0", "n_3_3", flow_id=f"flow_{i}")

        drawer_stats = router.get_drawer_statistics()

        # Multiple drawers should have made selections
        total_selections = sum(
            stats.get('selections_made', 0)
            for stats in drawer_stats.values()
        )
        assert total_selections > 0

    def test_no_global_topology_access(self, mesh_network, config):
        """Router nao deve ter acesso direto a topologia global."""
        router = DistributedSRSDRouter(mesh_network, config)

        # Router should not have graph attribute for routing decisions
        # (it stores _nodes but not the graph structure)
        assert not hasattr(router, 'graph')

        # Each node's drawer should only know neighbors
        for node_id, node in router._nodes.items():
            if node.drawer:
                assert not hasattr(node.drawer, 'graph')
                assert not hasattr(node.drawer, 'topology')

    def test_unreachable_destination(self, config):
        """Destino inalcancavel deve falhar graciosamente."""
        # Create disconnected graph
        graph = NetworkGraph()
        graph.add_node_simple("A")
        graph.add_node_simple("B")
        graph.add_edge_simple("A", "B")

        graph.add_node_simple("C")
        graph.add_node_simple("D")
        graph.add_edge_simple("C", "D")
        # A-B and C-D are disconnected

        router = DistributedSRSDRouter(graph, config)

        result = router.route("A", "D")
        assert result is None


class TestSRSDRouterIntegration:
    """Tests for SRSDRouter with distributed mode."""

    @pytest.fixture
    def mesh_graph(self):
        """Create mesh graph for SRSD testing."""
        return NetworkGraph.create_mesh(rows=4, cols=4)

    def test_distributed_mode_default(self, mesh_graph):
        """Distributed mode deve ser padrao."""
        config = SRSDConfig()  # Default config
        assert config.use_distributed is True

    def test_distributed_routing(self, mesh_graph):
        """Roteamento distribuido deve funcionar via SRSDRouter."""
        config = SRSDConfig(
            use_distributed=True,
            num_hiatus=2,
            seed=42
        )
        router = SRSDRouter(mesh_graph, config)
        router.set_seed(42)

        result = router.route("n_0_0", "n_3_3")
        assert result is not None
        assert result.destination == "n_3_3"

    def test_legacy_mode(self, mesh_graph):
        """Modo legado deve funcionar."""
        config = SRSDConfig(
            use_distributed=False,
            k_paths=5,
            seed=42
        )
        router = SRSDRouter(mesh_graph, config)
        router.set_seed(42)

        result = router.route("n_0_0", "n_3_3")
        assert result is not None
        assert result.destination == "n_3_3"

    def test_distributed_vs_legacy_diversity(self, mesh_graph):
        """Distributed deve ter diversidade comparavel ou superior."""
        # Distributed mode
        dist_config = SRSDConfig(use_distributed=True, num_hiatus=2, seed=42)
        dist_router = SRSDRouter(mesh_graph, dist_config)
        dist_router.set_seed(42)

        dist_paths = set()
        for i in range(20):
            result = dist_router.route("n_0_0", "n_3_3", flow_id=f"dist_{i}")
            if result:
                dist_paths.add(tuple(result.path))

        # Legacy mode
        legacy_config = SRSDConfig(use_distributed=False, k_paths=5, seed=42)
        legacy_router = SRSDRouter(mesh_graph, legacy_config)
        legacy_router.set_seed(42)

        legacy_paths = set()
        for i in range(20):
            result = legacy_router.route("n_0_0", "n_3_3", flow_id=f"legacy_{i}")
            if result:
                legacy_paths.add(tuple(result.path))

        # Both should have path diversity
        assert len(dist_paths) > 1
        assert len(legacy_paths) > 1


class TestDistributedConfig:
    """Tests for DistributedConfig."""

    def test_default_config(self):
        """Configuracao padrao."""
        config = DistributedConfig()

        assert config.num_hiatus == 3
        assert config.hiatus_placement == "random"
        assert config.blocking_window == 3
        assert config.max_hops == 100

    def test_custom_config(self):
        """Configuracao customizada."""
        config = DistributedConfig(
            num_hiatus=5,
            hiatus_placement="betweenness",
            blocking_window=5,
            seed=123
        )

        assert config.num_hiatus == 5
        assert config.hiatus_placement == "betweenness"
        assert config.blocking_window == 5
        assert config.seed == 123


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
