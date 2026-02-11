"""
Hiatus - CAR (Conversor de Alteracao de Rota).

Implements structural discontinuity points in the network.
Hiatus nodes break path correlation by:
1. Peeling onion layers
2. Adding mixing delays
3. Resetting routing context (forgetting where packet came from)
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional
import random
import time

if TYPE_CHECKING:
    from .packet import Packet, NextHopInfo


@dataclass
class HiatusStatistics:
    """Statistics for Hiatus operations."""

    packets_processed: int = 0
    layers_peeled: int = 0
    final_destinations_reached: int = 0
    total_mixing_delay: float = 0.0

    def record_process(self, added_delay: float, is_final: bool) -> None:
        """Record packet processing."""
        self.packets_processed += 1
        self.layers_peeled += 1
        self.total_mixing_delay += added_delay
        if is_final:
            self.final_destinations_reached += 1

    @property
    def avg_mixing_delay(self) -> float:
        """Average mixing delay per packet."""
        if self.packets_processed == 0:
            return 0.0
        return self.total_mixing_delay / self.packets_processed

    def reset(self) -> None:
        """Reset all statistics."""
        self.packets_processed = 0
        self.layers_peeled = 0
        self.final_destinations_reached = 0
        self.total_mixing_delay = 0.0


class HiatusController:
    """
    CAR - Conversor de Alteracao de Rota.

    Structural discontinuity point that:
    1. Peels onion layers from packets
    2. Adds mixing delay to break temporal correlation
    3. Resets routing context (forgets previous hop)

    Key security properties:
    - No node sees both origin and destination
    - Path segments are independent
    - Temporal correlation is broken
    """

    def __init__(self, node_id: str,
                 mixing_delay_mean: float = 0.01,
                 mixing_delay_std: float = 0.005,
                 seed: Optional[int] = None):
        """
        Initialize HiatusController.

        Args:
            node_id: ID of the Hiatus node
            mixing_delay_mean: Mean mixing delay in seconds
            mixing_delay_std: Standard deviation of mixing delay
            seed: Random seed for reproducibility
        """
        self.node_id = node_id
        self.mixing_delay_mean = mixing_delay_mean
        self.mixing_delay_std = mixing_delay_std

        # Statistics
        self.stats = HiatusStatistics()

        # Random state
        self._rng = random.Random(seed)

        # Packet queue for mixing (simulated)
        self._packet_queue: List[Dict] = []

    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._rng.seed(seed)

    def process_packet(self, packet: 'Packet') -> 'NextHopInfo':
        """
        Process a packet through the Hiatus.

        1. Add mixing delay (breaks temporal correlation)
        2. Peel onion layer (get next segment destination)
        3. Reset context (forget where packet came from)

        Args:
            packet: The packet to process

        Returns:
            NextHopInfo with the next segment destination
        """
        # Import here to avoid circular import
        from .packet import NextHopInfo

        # 1. Add mixing delay
        delay = self._add_mixing_delay()

        # 2. Peel onion layer
        next_info = packet.peel_layer()

        if next_info is None:
            # No more layers - this shouldn't happen in normal operation
            return NextHopInfo(
                segment_destination=self.node_id,
                is_final=True,
                added_delay=delay
            )

        # Record statistics
        self.stats.record_process(delay, next_info.is_final)

        # 3. Context is reset implicitly - we don't store/return previous hop info
        return NextHopInfo(
            segment_destination=next_info.segment_destination,
            is_final=next_info.is_final,
            added_delay=delay
        )

    def _add_mixing_delay(self) -> float:
        """
        Add mixing delay to break temporal correlation.

        Returns the delay added (for metrics).
        """
        delay = max(0, self._rng.gauss(self.mixing_delay_mean, self.mixing_delay_std))
        return delay

    def simulate_mixing(self, num_packets: int = 10) -> List[int]:
        """
        Simulate packet mixing/reordering.

        In a real implementation, packets would be queued and
        released in random order. Here we simulate the permutation.

        Args:
            num_packets: Number of packets to mix

        Returns:
            List representing the output order (indices of input packets)
        """
        order = list(range(num_packets))
        self._rng.shuffle(order)
        return order

    def get_path_expansion_factor(self, num_neighbors: int, num_segments: int) -> int:
        """
        Calculate the path expansion factor provided by Hiatus structure.

        With k neighbors per node and n segments (n-1 Hiatus nodes),
        the number of possible paths is k^n.

        Args:
            num_neighbors: Average number of neighbors per node
            num_segments: Number of path segments (Hiatus nodes + 1)

        Returns:
            Number of possible distinct paths
        """
        return num_neighbors ** num_segments

    def reset(self) -> None:
        """Reset Hiatus state."""
        self._packet_queue.clear()
        self.stats.reset()

    def get_statistics(self) -> Dict:
        """Get Hiatus statistics."""
        return {
            'node_id': self.node_id,
            'packets_processed': self.stats.packets_processed,
            'layers_peeled': self.stats.layers_peeled,
            'final_destinations': self.stats.final_destinations_reached,
            'avg_mixing_delay': self.stats.avg_mixing_delay,
            'total_mixing_delay': self.stats.total_mixing_delay,
        }


def select_hiatus_nodes(graph: 'NetworkGraph', num_hiatus: int,
                        strategy: str = "random",
                        seed: Optional[int] = None) -> List[str]:
    """
    Select nodes to serve as Hiatus (CAR) points.

    Args:
        graph: NetworkGraph instance
        num_hiatus: Number of Hiatus nodes to select
        strategy: Selection strategy ("random", "betweenness", "degree")
        seed: Random seed for reproducibility

    Returns:
        List of node IDs selected as Hiatus nodes
    """
    nodes = [n.id for n in graph.get_nodes()]

    if num_hiatus >= len(nodes):
        return nodes

    rng = random.Random(seed)

    if strategy == "random":
        return rng.sample(nodes, num_hiatus)

    elif strategy == "betweenness":
        # Select nodes with highest betweenness centrality
        # These are natural "waypoints" in the network
        import networkx as nx
        centrality = nx.betweenness_centrality(graph._graph)
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        return [node_id for node_id, _ in sorted_nodes[:num_hiatus]]

    elif strategy == "degree":
        # Select nodes with highest degree (most connections)
        degrees = [(n.id, len(graph.get_neighbors(n.id))) for n in graph.get_nodes()]
        sorted_nodes = sorted(degrees, key=lambda x: x[1], reverse=True)
        return [node_id for node_id, _ in sorted_nodes[:num_hiatus]]

    else:
        raise ValueError(f"Unknown Hiatus selection strategy: {strategy}")


def calculate_hiatus_coverage(graph: 'NetworkGraph', hiatus_ids: List[str]) -> Dict:
    """
    Calculate metrics about Hiatus coverage in the network.

    Args:
        graph: NetworkGraph instance
        hiatus_ids: List of Hiatus node IDs

    Returns:
        Dictionary with coverage metrics
    """
    total_nodes = graph.num_nodes
    num_hiatus = len(hiatus_ids)

    # Calculate average distance to nearest Hiatus
    # (simplified - would need proper path calculation in production)
    coverage_ratio = num_hiatus / total_nodes if total_nodes > 0 else 0

    # Estimate path expansion
    avg_degree = sum(len(graph.get_neighbors(n.id)) for n in graph.get_nodes()) / total_nodes
    path_expansion = avg_degree ** (num_hiatus + 1)

    return {
        'total_nodes': total_nodes,
        'num_hiatus': num_hiatus,
        'coverage_ratio': coverage_ratio,
        'estimated_path_expansion': path_expansion,
        'avg_node_degree': avg_degree,
    }
