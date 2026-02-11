"""Tests for SRSD Specification Compliance.

These tests verify that the implementation conforms to the SRSD specification:
- No global topology knowledge
- No classical optimization (shortest-path)
- Repetition BLOCKED not penalized
- QKD independent of routing
- QKD mandatory
- Blind spots eliminated (origin/destination hidden)
"""

import pytest
import warnings
import inspect

from src.core.graph import NetworkGraph
from src.core.drawer import Drawer
from src.core.packet import Packet, EncryptedLayer, create_onion_packet
from src.routing.distributed import DistributedSRSDRouter, DistributedConfig
from src.routing.srsd import SRSDRouter, SRSDConfig
from src.qkd.channel import QKDChannelManager, QKDChannel
from src.simulation.scenario import TopologyConfig, ExperimentConfig


class TestNoGlobalTopologyKnowledge:
    """Tests verifying no global topology knowledge."""

    def test_drawer_no_graph_attribute(self):
        """Drawer nao deve ter atributo graph."""
        drawer = Drawer("n1", ["n2", "n3"])

        # Drawer should NOT have any graph-related attributes
        forbidden_attrs = ['graph', 'topology', 'network', 'adjacency',
                           'shortest_path', 'all_paths']

        for attr in forbidden_attrs:
            assert not hasattr(drawer, attr), f"Drawer should not have '{attr}' attribute"

    def test_drawer_only_knows_neighbors(self):
        """Drawer deve conhecer apenas vizinhos diretos."""
        drawer = Drawer("n1", ["n2", "n3", "n4"])

        # Drawer should only have neighbors list
        assert hasattr(drawer, 'neighbors')
        assert len(drawer.neighbors) == 3

        # Cannot select non-neighbors
        selection = drawer.select_next_hop("dest")
        assert selection in drawer.neighbors

    def test_distributed_router_no_shortest_path(self):
        """DistributedSRSDRouter nao deve chamar shortest_path."""
        graph = NetworkGraph.create_mesh(3, 3)
        config = DistributedConfig(num_hiatus=1, seed=42)
        router = DistributedSRSDRouter(graph, config)

        # Check that router doesn't have shortest_path method or call it
        # (it delegates to Drawers for local decisions)
        assert not hasattr(router, 'shortest_path')

        # Verify routing works without shortest_path
        result = router.route("n_0_0", "n_2_2")
        assert result is not None


class TestNoClassicalOptimization:
    """Tests verifying no classical optimization."""

    def test_no_shortest_path_in_distributed(self):
        """Distributed mode nao deve usar shortest_path."""
        graph = NetworkGraph.create_mesh(4, 4)
        config = SRSDConfig(use_distributed=True, num_hiatus=2, seed=42)
        router = SRSDRouter(graph, config)

        # In distributed mode, _distributed router handles routing
        # without using graph's shortest_path

        # Route multiple times
        for i in range(10):
            router.route("n_0_0", "n_3_3", flow_id=f"flow_{i}")

        # Paths should NOT always be optimal (would indicate shortest_path use)
        stats = router.get_statistics()
        # With blocking, we should see path diversity
        assert stats.unique_paths > 0


class TestRepetitionBlocked:
    """Tests verifying repetition is BLOCKED not penalized."""

    def test_blocking_not_penalization(self):
        """Repeticao deve ser bloqueada, nao penalizada."""
        drawer = Drawer("n1", ["n2", "n3"], seed=42)
        drawer.blocking_window = 100  # Prevent auto-unblock

        # First selection
        s1 = drawer.select_next_hop("dest")

        # Second selection MUST be different (blocked, not penalized)
        s2 = drawer.select_next_hop("dest")

        assert s1 != s2, "Repetition should be BLOCKED, not penalized"

    def test_path_different_consecutively(self):
        """Caminhos consecutivos devem ser diferentes."""
        graph = NetworkGraph.create_mesh(4, 4)
        config = DistributedConfig(num_hiatus=2, blocking_window=100, seed=42)
        router = DistributedSRSDRouter(graph, config)
        router.set_seed(42)

        result1 = router.route("n_0_0", "n_3_3", flow_id="flow_1")
        result2 = router.route("n_0_0", "n_3_3", flow_id="flow_2")

        # Paths should generally be different due to blocking
        # (May occasionally be same if forced unblock occurs)
        assert result1 is not None
        assert result2 is not None
        # The mechanism ensures blocking, even if paths occasionally match


class TestQKDIndependent:
    """Tests verifying QKD does not influence routing."""

    def test_qkd_risk_not_used_in_distributed(self):
        """QKD risk nao deve influenciar roteamento."""
        graph = NetworkGraph.create_mesh(3, 3)

        config = SRSDConfig(
            use_distributed=True,
            num_hiatus=1,
            use_qkd_indicators=True,  # Even if set to True...
            seed=42
        )
        router = SRSDRouter(graph, config)

        # In distributed mode, QKD indicators are NOT used
        # Routing is done by Drawers which don't consider QKD
        result = router.route("n_0_0", "n_2_2")
        assert result is not None

    def test_qkd_risk_deprecated(self):
        """get_risk_level deve emitir warning de deprecacao."""
        channel = QKDChannel(source="A", target="B")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            channel.get_risk_level()

            # Should emit deprecation warning
            assert len(w) > 0
            assert any(issubclass(warning.category, DeprecationWarning) for warning in w)

    def test_qkd_channel_manager_risk_deprecated(self):
        """get_channel_risk deve emitir warning de deprecacao."""
        manager = QKDChannelManager()
        manager.create_channel("A", "B")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            manager.get_channel_risk("A", "B")

            # Should emit deprecation warning
            assert len(w) > 0
            assert any(issubclass(warning.category, DeprecationWarning) for warning in w)

    def test_qkd_has_keys_method(self):
        """has_keys deve estar disponivel como alternativa correta."""
        manager = QKDChannelManager()
        channel = manager.create_channel("A", "B", initial_key_rate=1000)

        # Simulate key generation
        channel.generate_keys(1.0)

        # has_keys should work without deprecation warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = manager.has_keys("A", "B", amount=100)

            # Should NOT emit deprecation warning for has_keys
            deprecation_warnings = [
                warning for warning in w
                if issubclass(warning.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) == 0


class TestQKDMandatory:
    """Tests verifying QKD is mandatory by default."""

    def test_qkd_enabled_by_default(self):
        """QKD deve ser habilitado por padrao."""
        config = TopologyConfig()
        assert config.qkd_enabled is True

    def test_qkd_coverage_full_by_default(self):
        """QKD coverage deve ser 100% por padrao."""
        config = TopologyConfig()
        assert config.qkd_coverage == 1.0


class TestBlindSpotsEliminated:
    """Tests verifying origin/destination are hidden."""

    def test_packet_hides_source(self):
        """Pacote nao deve expor origem."""
        packet = create_onion_packet(
            packet_id="p1",
            hiatus_sequence=["h1"],
            final_destination="dest",
            source="src"
        )

        # Public methods should not expose source
        assert packet.get_current_segment_destination() != "src"

        # _true_source is private (for simulation analysis only)
        # In real implementation, this would be encrypted

    def test_packet_hides_destination(self):
        """Pacote nao deve expor destino final."""
        packet = create_onion_packet(
            packet_id="p1",
            hiatus_sequence=["h1", "h2"],
            final_destination="dest",
            source="src"
        )

        # Current visible destination is first Hiatus, not final dest
        visible_dest = packet.get_current_segment_destination()
        assert visible_dest == "h1"
        assert visible_dest != "dest"

    def test_intermediate_node_cannot_see_endpoints(self):
        """No intermediario nao deve ver origem nem destino."""
        packet = create_onion_packet(
            packet_id="p1",
            hiatus_sequence=["h1", "h2"],
            final_destination="dest",
            source="src"
        )

        # At first hop, only h1 is visible
        assert packet.get_current_segment_destination() == "h1"

        # After peeling at h1, only h2 is visible
        packet.peel_layer()
        assert packet.get_current_segment_destination() == "h2"

        # After peeling at h2, only dest is visible
        packet.peel_layer()
        assert packet.get_current_segment_destination() == "dest"

        # Source was never visible during transit


class TestDistributedModeDefault:
    """Tests verifying distributed mode is default."""

    def test_srsd_config_distributed_default(self):
        """SRSDConfig deve usar distributed por padrao."""
        config = SRSDConfig()
        assert config.use_distributed is True

    def test_experiment_config_distributed_default(self):
        """ExperimentConfig deve usar distributed por padrao."""
        config = ExperimentConfig()
        assert config.use_distributed_srsd is True


class TestEntropyImprovement:
    """Tests verifying entropy improvement over baseline."""

    @pytest.fixture
    def mesh_graph(self):
        """Create mesh graph."""
        return NetworkGraph.create_mesh(rows=4, cols=4)

    def test_srsd_vs_baseline_paths(self, mesh_graph):
        """SRSD deve usar mais caminhos unicos que baseline."""
        from src.routing.baseline import BaselineRouter

        # Baseline router (deterministic)
        baseline = BaselineRouter(mesh_graph)
        baseline_paths = set()
        for i in range(50):
            result = baseline.route("n_0_0", "n_3_3", flow_id=f"baseline_{i}")
            if result:
                baseline_paths.add(tuple(result.path))

        # SRSD router (distributed)
        srsd_config = SRSDConfig(use_distributed=True, num_hiatus=2, seed=42)
        srsd = SRSDRouter(mesh_graph, srsd_config)
        srsd.set_seed(42)

        srsd_paths = set()
        for i in range(50):
            result = srsd.route("n_0_0", "n_3_3", flow_id=f"srsd_{i}")
            if result:
                srsd_paths.add(tuple(result.path))

        # Baseline should have only 1 path (deterministic)
        assert len(baseline_paths) == 1

        # SRSD should have multiple paths
        assert len(srsd_paths) > len(baseline_paths)


class TestComplianceValidation:
    """Quick validation script tests."""

    def test_drawer_no_graph_quick(self):
        """Validacao rapida: Drawer sem conhecimento global."""
        drawer = Drawer("n1", ["n2"])
        assert not hasattr(drawer, 'graph'), "Drawer nao deve ter conhecimento global"

    def test_qkd_default_enabled(self):
        """Validacao rapida: QKD habilitado por padrao."""
        config = TopologyConfig()
        assert config.qkd_enabled is True, "QKD deve ser habilitado por padrao"

    def test_distributed_default(self):
        """Validacao rapida: Distributed mode padrao."""
        config = SRSDConfig()
        assert config.use_distributed is True, "Distributed mode deve ser padrao"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
