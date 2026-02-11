"""Tests for Drawer - local routing gateway."""

import pytest

from src.core.drawer import Drawer, initialize_drawers_from_graph
from src.core.graph import NetworkGraph


class TestDrawer:
    """Tests for Drawer class."""

    def test_neighbor_blocking(self):
        """Vizinho selecionado deve ser bloqueado."""
        drawer = Drawer("n1", ["n2", "n3", "n4"], seed=42)

        selected = drawer.select_next_hop("dest")
        assert selected in ["n2", "n3", "n4"]
        assert selected in drawer.blocked.get("dest", set())

    def test_no_repetition_until_exhausted(self):
        """Nao repete vizinho ate esgotar alternativas."""
        drawer = Drawer("n1", ["n2", "n3"], seed=42)
        drawer.blocking_window = 10  # Long window to prevent auto-unblock

        # First two selections must be different
        s1 = drawer.select_next_hop("dest")
        s2 = drawer.select_next_hop("dest")

        assert s1 != s2
        assert s1 in ["n2", "n3"]
        assert s2 in ["n2", "n3"]

    def test_forced_unblock(self):
        """Desbloqueio forcado quando todos bloqueados."""
        drawer = Drawer("n1", ["n2"], seed=42)
        drawer.blocking_window = 100  # Prevent auto-unblock

        # First selection blocks the only neighbor
        s1 = drawer.select_next_hop("dest")
        assert s1 == "n2"

        # Second selection must force unblock
        s2 = drawer.select_next_hop("dest")
        assert s2 == "n2"

        # Stats should show forced unblock
        assert drawer.stats.forced_unblocks >= 1

    def test_no_global_knowledge(self):
        """Drawer nao deve ter acesso a topologia global."""
        drawer = Drawer("n1", ["n2", "n3"])

        # Drawer should NOT have graph/topology attributes
        assert not hasattr(drawer, 'graph')
        assert not hasattr(drawer, 'topology')
        assert not hasattr(drawer, 'network')

        # Drawer should only know its neighbors
        assert hasattr(drawer, 'neighbors')
        assert len(drawer.neighbors) == 2

    def test_only_knows_neighbors(self):
        """Drawer deve conhecer apenas vizinhos diretos."""
        drawer = Drawer("n1", ["n2", "n3"])

        # Drawer should not be able to select non-neighbors
        assert drawer.select_next_hop("dest") in ["n2", "n3"]

    def test_blocking_is_per_destination(self):
        """Bloqueio deve ser por destino."""
        drawer = Drawer("n1", ["n2", "n3", "n4"], seed=42)
        drawer.blocking_window = 100

        # Select for destination A
        s_a1 = drawer.select_next_hop("dest_A")
        s_a2 = drawer.select_next_hop("dest_A")

        # Select for destination B - should have all options available
        s_b1 = drawer.select_next_hop("dest_B")

        # For dest_A, both selections should be different
        assert s_a1 != s_a2

        # dest_B should have all neighbors available initially
        assert drawer.get_eligible_count("dest_B") == 2  # One was just selected

    def test_unblock_all(self):
        """Desbloqueio total para destino."""
        drawer = Drawer("n1", ["n2", "n3"], seed=42)
        drawer.blocking_window = 100

        drawer.select_next_hop("dest")
        drawer.select_next_hop("dest")

        # Both should be blocked now
        assert drawer.get_blocked_count("dest") == 2

        drawer.unblock_all("dest")
        assert drawer.get_blocked_count("dest") == 0

    def test_statistics(self):
        """Estatisticas devem ser registradas."""
        drawer = Drawer("n1", ["n2", "n3"], seed=42)

        for _ in range(5):
            drawer.select_next_hop("dest")

        stats = drawer.get_statistics()
        assert stats['selections_made'] == 5
        assert stats['num_neighbors'] == 2

    def test_reset(self):
        """Reset deve limpar estado."""
        drawer = Drawer("n1", ["n2", "n3"], seed=42)
        drawer.blocking_window = 100

        drawer.select_next_hop("dest")
        drawer.select_next_hop("dest")

        drawer.reset()

        assert drawer.get_blocked_count("dest") == 0
        assert drawer.stats.selections_made == 0

    def test_empty_neighbors(self):
        """Drawer sem vizinhos deve retornar None."""
        drawer = Drawer("n1", [])

        result = drawer.select_next_hop("dest")
        assert result is None
        assert drawer.stats.no_eligible_count == 1

    def test_deterministic_with_seed(self):
        """Mesma seed deve produzir mesma sequencia."""
        drawer1 = Drawer("n1", ["n2", "n3", "n4"], seed=42)
        drawer1.blocking_window = 100

        drawer2 = Drawer("n1", ["n2", "n3", "n4"], seed=42)
        drawer2.blocking_window = 100

        selections1 = [drawer1.select_next_hop("dest") for _ in range(3)]
        selections2 = [drawer2.select_next_hop("dest") for _ in range(3)]

        assert selections1 == selections2


class TestDrawerInitialization:
    """Tests for Drawer initialization from graph."""

    @pytest.fixture
    def mesh_graph(self):
        """Create a 3x3 mesh graph."""
        return NetworkGraph.create_mesh(rows=3, cols=3)

    def test_initialize_from_graph(self, mesh_graph):
        """Drawers devem ser inicializados para todos os nos."""
        drawers = initialize_drawers_from_graph(mesh_graph)

        # Should have one drawer per node
        assert len(drawers) == 9  # 3x3 mesh

        # Each drawer should know its neighbors
        for node_id, drawer in drawers.items():
            assert drawer.node_id == node_id
            expected_neighbors = mesh_graph.get_neighbors(node_id)
            assert set(drawer.neighbors) == set(expected_neighbors)

    def test_corner_nodes_have_fewer_neighbors(self, mesh_graph):
        """Nos de canto devem ter menos vizinhos."""
        drawers = initialize_drawers_from_graph(mesh_graph)

        # Corner node n_0_0 should have 2 neighbors
        corner_drawer = drawers["n_0_0"]
        assert len(corner_drawer.neighbors) == 2

        # Center node n_1_1 should have 4 neighbors
        center_drawer = drawers["n_1_1"]
        assert len(center_drawer.neighbors) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
