"""Tests for Hiatus - CAR (Conversor de Alteracao de Rota)."""

import pytest

from src.core.hiatus import HiatusController, select_hiatus_nodes, calculate_hiatus_coverage
from src.core.packet import Packet, EncryptedLayer, create_onion_packet
from src.core.graph import NetworkGraph


class TestHiatusController:
    """Tests for HiatusController class."""

    def test_layer_peeling(self):
        """Hiatus deve descascar camada do pacote."""
        packet = Packet(
            packet_id="p1",
            layers=[
                EncryptedLayer("hiatus1", False),
                EncryptedLayer("destination", True)
            ]
        )

        controller = HiatusController("hiatus1", seed=42)
        next_info = controller.process_packet(packet)

        assert next_info.segment_destination == "destination"
        assert next_info.is_final is True

    def test_multiple_layers(self):
        """Hiatus deve processar multiplas camadas em sequencia."""
        packet = Packet(
            packet_id="p1",
            layers=[
                EncryptedLayer("hiatus1", False),
                EncryptedLayer("hiatus2", False),
                EncryptedLayer("destination", True)
            ]
        )

        # First Hiatus peels first layer
        controller1 = HiatusController("hiatus1", seed=42)
        next_info1 = controller1.process_packet(packet)

        assert next_info1.segment_destination == "hiatus2"
        assert next_info1.is_final is False

        # Second Hiatus peels second layer
        controller2 = HiatusController("hiatus2", seed=42)
        next_info2 = controller2.process_packet(packet)

        assert next_info2.segment_destination == "destination"
        assert next_info2.is_final is True

    def test_mixing_delay_added(self):
        """Hiatus deve adicionar delay de mixing."""
        packet = Packet(
            packet_id="p1",
            layers=[EncryptedLayer("dest", True)]
        )

        controller = HiatusController("hiatus1", mixing_delay_mean=0.1, seed=42)
        next_info = controller.process_packet(packet)

        # Delay should be added
        assert next_info.added_delay >= 0
        assert controller.stats.total_mixing_delay > 0

    def test_context_reset(self):
        """Hiatus deve resetar contexto de roteamento."""
        packet = create_onion_packet(
            packet_id="p1",
            hiatus_sequence=["hiatus1"],
            final_destination="dest",
            source="origin"
        )

        controller = HiatusController("hiatus1", seed=42)
        next_info = controller.process_packet(packet)

        # next_info should NOT contain source information
        # Only segment_destination and is_final
        assert hasattr(next_info, 'segment_destination')
        assert hasattr(next_info, 'is_final')
        # No source/origin info in result
        assert not hasattr(next_info, 'source')
        assert not hasattr(next_info, 'origin')

    def test_statistics(self):
        """Estatisticas devem ser registradas."""
        controller = HiatusController("hiatus1", seed=42)

        for i in range(5):
            packet = Packet(
                packet_id=f"p{i}",
                layers=[EncryptedLayer("dest", True)]
            )
            controller.process_packet(packet)

        stats = controller.get_statistics()
        assert stats['packets_processed'] == 5
        assert stats['layers_peeled'] == 5
        assert stats['final_destinations'] == 5

    def test_path_expansion_factor(self):
        """Adicao de Hiatus deve expandir espaco de caminhos."""
        controller = HiatusController("hiatus1")

        # With 3 neighbors per node and 2 segments (1 Hiatus):
        # Possible paths = 3^2 = 9
        expansion = controller.get_path_expansion_factor(num_neighbors=3, num_segments=2)
        assert expansion == 9

        # With 3 neighbors per node and 3 segments (2 Hiatus):
        # Possible paths = 3^3 = 27
        expansion = controller.get_path_expansion_factor(num_neighbors=3, num_segments=3)
        assert expansion == 27

    def test_reset(self):
        """Reset deve limpar estado."""
        controller = HiatusController("hiatus1", seed=42)

        packet = Packet(
            packet_id="p1",
            layers=[EncryptedLayer("dest", True)]
        )
        controller.process_packet(packet)

        controller.reset()

        assert controller.stats.packets_processed == 0
        assert controller.stats.total_mixing_delay == 0.0


class TestHiatusSelection:
    """Tests for Hiatus node selection."""

    @pytest.fixture
    def mesh_graph(self):
        """Create a 4x4 mesh graph."""
        return NetworkGraph.create_mesh(rows=4, cols=4)

    def test_random_selection(self, mesh_graph):
        """Selecao aleatoria de Hiatus."""
        hiatus_ids = select_hiatus_nodes(mesh_graph, num_hiatus=3, strategy="random", seed=42)

        assert len(hiatus_ids) == 3
        # All selected should be valid nodes
        node_ids = {n.id for n in mesh_graph.get_nodes()}
        assert all(h in node_ids for h in hiatus_ids)

    def test_betweenness_selection(self, mesh_graph):
        """Selecao por betweenness centrality."""
        hiatus_ids = select_hiatus_nodes(mesh_graph, num_hiatus=3, strategy="betweenness")

        assert len(hiatus_ids) == 3
        # Center nodes should be more likely to be selected

    def test_degree_selection(self, mesh_graph):
        """Selecao por grau do no."""
        hiatus_ids = select_hiatus_nodes(mesh_graph, num_hiatus=3, strategy="degree")

        assert len(hiatus_ids) == 3
        # High-degree nodes should be selected

    def test_max_hiatus_limit(self, mesh_graph):
        """Nao deve selecionar mais Hiatus que nos disponiveis."""
        hiatus_ids = select_hiatus_nodes(mesh_graph, num_hiatus=100, strategy="random")

        # Should be limited to total nodes
        assert len(hiatus_ids) == mesh_graph.num_nodes

    def test_deterministic_with_seed(self, mesh_graph):
        """Mesma seed deve produzir mesma selecao."""
        hiatus1 = select_hiatus_nodes(mesh_graph, num_hiatus=3, strategy="random", seed=42)
        hiatus2 = select_hiatus_nodes(mesh_graph, num_hiatus=3, strategy="random", seed=42)

        assert hiatus1 == hiatus2


class TestHiatusCoverage:
    """Tests for Hiatus coverage metrics."""

    @pytest.fixture
    def mesh_graph(self):
        """Create a 4x4 mesh graph."""
        return NetworkGraph.create_mesh(rows=4, cols=4)

    def test_coverage_calculation(self, mesh_graph):
        """Calculo de cobertura de Hiatus."""
        hiatus_ids = select_hiatus_nodes(mesh_graph, num_hiatus=4, strategy="random", seed=42)
        coverage = calculate_hiatus_coverage(mesh_graph, hiatus_ids)

        assert coverage['total_nodes'] == 16  # 4x4 mesh
        assert coverage['num_hiatus'] == 4
        assert coverage['coverage_ratio'] == 4 / 16

    def test_path_expansion_estimation(self, mesh_graph):
        """Estimativa de expansao de caminhos."""
        hiatus_ids = select_hiatus_nodes(mesh_graph, num_hiatus=2, strategy="random", seed=42)
        coverage = calculate_hiatus_coverage(mesh_graph, hiatus_ids)

        # Should have positive path expansion
        assert coverage['estimated_path_expansion'] > 1


class TestPacketWithHiatus:
    """Tests for packet structure with Hiatus."""

    def test_onion_packet_creation(self):
        """Criacao de pacote onion com Hiatus."""
        packet = create_onion_packet(
            packet_id="p1",
            hiatus_sequence=["h1", "h2"],
            final_destination="dest",
            source="src"
        )

        assert packet.total_layers == 3  # h1, h2, dest
        assert packet.remaining_layers == 3

    def test_onion_packet_peeling(self):
        """Descascamento de pacote onion."""
        packet = create_onion_packet(
            packet_id="p1",
            hiatus_sequence=["h1", "h2"],
            final_destination="dest"
        )

        # First peel: h1
        info1 = packet.peel_layer()
        assert info1.segment_destination == "h1"
        assert info1.is_final is False

        # Second peel: h2
        info2 = packet.peel_layer()
        assert info2.segment_destination == "h2"
        assert info2.is_final is False

        # Third peel: dest (final)
        info3 = packet.peel_layer()
        assert info3.segment_destination == "dest"
        assert info3.is_final is True

        # No more layers
        info4 = packet.peel_layer()
        assert info4 is None

    def test_packet_hides_origin_destination(self):
        """Pacote deve ocultar origem e destino."""
        packet = create_onion_packet(
            packet_id="p1",
            hiatus_sequence=["h1"],
            final_destination="dest",
            source="src"
        )

        # Current visible destination should be h1 (first Hiatus)
        assert packet.get_current_segment_destination() == "h1"

        # True source/dest are in private fields (for simulation only)
        # These should NOT be accessible to routing decisions
        assert packet._true_source == "src"
        assert packet._true_destination == "dest"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
