"""
Distributed SRSD Router - Coordenador de Roteamento Distribuido.

Implements the true SRSD specification:
- NO global topology knowledge
- Local decisions via Drawer
- Structural discontinuity via Hiatus
- Onion packet structure for blind spots
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import random
import time

from ..core.graph import NetworkGraph
from ..core.node import Node, NodeType
from ..core.drawer import Drawer, initialize_drawers_from_graph
from ..core.hiatus import HiatusController, select_hiatus_nodes
from ..core.packet import (
    Packet, EncryptedLayer, NextHopInfo, ForwardingTrace,
    create_onion_packet, generate_packet_id
)
from .baseline import FlowRecord, RoutingStatistics


# Maximum hops before considering packet lost
MAX_HOPS = 100


@dataclass
class DistributedConfig:
    """Configuration for distributed SRSD routing."""

    # Hiatus configuration
    num_hiatus: int = 3
    hiatus_placement: str = "random"  # "random", "betweenness", "degree"

    # Drawer configuration
    blocking_window: int = 3

    # Mixing configuration
    mixing_delay_mean: float = 0.01
    mixing_delay_std: float = 0.005

    # Limits
    max_hops: int = MAX_HOPS

    # Random seed
    seed: Optional[int] = None


@dataclass
class FlowResult:
    """Result of routing a single flow through the distributed system."""

    flow_id: str
    trace: ForwardingTrace
    success: bool
    total_delay: float = 0.0
    hiatus_visited: List[str] = field(default_factory=list)

    # Hidden metadata (for analysis only, not visible to network)
    _source: Optional[str] = None
    _destination: Optional[str] = None


class DistributedSRSDRouter:
    """
    Coordenador de Roteamento Distribuido.

    This is the core SRSD implementation that conforms to the specification:

    1. NO global topology knowledge - each node only knows its neighbors
    2. Routing decisions are made locally by Drawers
    3. Hiatus nodes provide structural discontinuity
    4. Packets use onion structure to hide origin/destination

    Key differences from the legacy router:
    - Does NOT use shortest_path or any global graph algorithms
    - Does NOT have access to complete topology
    - Routes hop-by-hop using local decisions
    """

    def __init__(self, graph: NetworkGraph, config: Optional[DistributedConfig] = None,
                 hiatus_ids: Optional[Set[str]] = None):
        """
        Initialize Distributed SRSD Router.

        Args:
            graph: NetworkGraph for topology information
            config: Configuration parameters
            hiatus_ids: Pre-selected Hiatus node IDs (or will be selected automatically)
        """
        self.config = config or DistributedConfig()
        self._rng = random.Random(self.config.seed)

        # Store node references (but NOT the graph structure)
        self._nodes: Dict[str, Node] = {n.id: n for n in graph.get_nodes()}

        # Initialize Drawers for all nodes
        self._initialize_drawers(graph)

        # Select or use provided Hiatus nodes
        if hiatus_ids is not None:
            self.hiatus_ids = set(hiatus_ids)
        else:
            self.hiatus_ids = set(select_hiatus_nodes(
                graph, self.config.num_hiatus,
                strategy=self.config.hiatus_placement,
                seed=self.config.seed
            ))

        # Initialize Hiatus controllers
        self._initialize_hiatus_controllers()

        # Statistics
        self.stats = RoutingStatistics()

    def _initialize_drawers(self, graph: NetworkGraph) -> None:
        """Initialize Drawers for all nodes using only local neighbor information."""
        for node_id, node in self._nodes.items():
            neighbors = graph.get_neighbors(node_id)
            node.initialize_drawer(
                neighbors=neighbors,
                blocking_window=self.config.blocking_window,
                seed=self.config.seed
            )

    def _initialize_hiatus_controllers(self) -> None:
        """Initialize HiatusControllers for selected Hiatus nodes."""
        for hiatus_id in self.hiatus_ids:
            if hiatus_id in self._nodes:
                node = self._nodes[hiatus_id]
                node.node_type = NodeType.HIATUS
                node.initialize_hiatus_controller(
                    mixing_delay_mean=self.config.mixing_delay_mean,
                    mixing_delay_std=self.config.mixing_delay_std,
                    seed=self.config.seed
                )

    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._rng.seed(seed)
        for node in self._nodes.values():
            if node.drawer:
                node.drawer.set_seed(seed)
            if node.hiatus_controller:
                node.hiatus_controller.set_seed(seed)

    def route(self, source: str, destination: str,
              flow_id: Optional[str] = None) -> Optional[FlowRecord]:
        """
        Route a flow from source to destination using distributed SRSD.

        Process:
        1. Select Hiatus sequence for the path
        2. Create onion packet with segment destinations
        3. Simulate hop-by-hop forwarding using Drawer decisions
        4. Return FlowRecord for compatibility with existing code

        Args:
            source: Source node ID
            destination: Destination node ID
            flow_id: Optional flow identifier

        Returns:
            FlowRecord if successful, None if routing failed
        """
        timestamp = time.time()
        fid = flow_id or f"flow_{source}_{destination}_{timestamp}"

        # Validate source and destination
        if source not in self._nodes or destination not in self._nodes:
            self.stats.record_failure()
            return None

        # 1. Select Hiatus sequence for this flow
        hiatus_sequence = self._select_hiatus_sequence(source, destination)

        # 2. Create onion packet
        packet = create_onion_packet(
            packet_id=generate_packet_id(),
            hiatus_sequence=hiatus_sequence,
            final_destination=destination,
            source=source
        )

        # 3. Simulate hop-by-hop forwarding
        result = self._simulate_forwarding(packet, source)

        if not result.success:
            self.stats.record_failure()
            return None

        # 4. Convert to FlowRecord for compatibility
        flow = FlowRecord(
            flow_id=fid,
            source=source,
            destination=destination,
            path=result.trace.path,
            timestamp=timestamp,
            latency=result.total_delay,
        )

        self.stats.record_success(flow)
        return flow

    def _select_hiatus_sequence(self, source: str, destination: str) -> List[str]:
        """
        Select a sequence of Hiatus nodes for the path.

        The sequence defines the segment waypoints. Each segment
        is routed independently using local Drawer decisions.

        This is the ONLY place where we have some "global" view -
        knowing which nodes are Hiatus. However, we don't use
        topology information for selection, just random choice.
        """
        # Exclude source and destination from Hiatus selection
        available_hiatus = [
            h for h in self.hiatus_ids
            if h != source and h != destination
        ]

        if not available_hiatus:
            return []

        # Select a subset of Hiatus nodes (could be all or a random sample)
        num_to_use = min(len(available_hiatus), self.config.num_hiatus)
        selected = self._rng.sample(available_hiatus, num_to_use)

        # Shuffle to randomize order
        self._rng.shuffle(selected)

        return selected

    def _simulate_forwarding(self, packet: Packet, start_node: str) -> FlowResult:
        """
        Simulate hop-by-hop packet forwarding.

        Each hop is decided locally by the node's Drawer, which
        only knows about direct neighbors.
        """
        trace = ForwardingTrace()
        current_node = start_node
        total_delay = 0.0
        hiatus_visited = []

        # Get first segment destination from packet
        segment_dest = packet.get_current_segment_destination()
        if segment_dest is None:
            trace.mark_dropped("no_segment_destination")
            return FlowResult(
                flow_id=packet.packet_id,
                trace=trace,
                success=False
            )

        while trace.hop_count < self.config.max_hops:
            node = self._nodes.get(current_node)
            if node is None:
                trace.mark_dropped("node_not_found")
                break

            # Check if we've reached the current segment destination
            if current_node == segment_dest:
                # If this is a Hiatus node, process the packet
                if node.is_hiatus() and node.hiatus_controller:
                    hiatus_visited.append(current_node)
                    next_info = node.hiatus_controller.process_packet(packet)
                    total_delay += next_info.added_delay

                    if next_info.is_final:
                        # Reached final destination
                        trace.mark_reached()
                        break

                    # Update segment destination
                    segment_dest = next_info.segment_destination

                elif packet.peek_layer() and packet.peek_layer().is_final:
                    # Reached final destination (non-Hiatus)
                    trace.mark_reached()
                    break

                else:
                    # Non-Hiatus intermediate - shouldn't happen in normal operation
                    # Peel layer and continue
                    next_info = packet.peel_layer()
                    if next_info is None or next_info.is_final:
                        trace.mark_reached()
                        break
                    segment_dest = next_info.segment_destination

            # Use Drawer to select next hop (LOCAL DECISION ONLY)
            if node.drawer is None:
                trace.mark_dropped("no_drawer")
                break

            next_hop = node.drawer.select_next_hop(segment_dest)
            if next_hop is None:
                trace.mark_dropped("no_eligible_neighbor")
                break

            # Record the hop
            trace.add_hop(current_node, next_hop)
            current_node = next_hop

        # Check if we exceeded max hops
        if trace.hop_count >= self.config.max_hops and not trace.reached_destination:
            trace.mark_dropped("max_hops_exceeded")

        return FlowResult(
            flow_id=packet.packet_id,
            trace=trace,
            success=trace.reached_destination,
            total_delay=total_delay,
            hiatus_visited=hiatus_visited,
            _source=packet._true_source,
            _destination=packet._true_destination
        )

    def get_statistics(self) -> RoutingStatistics:
        """Get routing statistics."""
        return self.stats

    def get_drawer_statistics(self) -> Dict[str, Dict]:
        """Get statistics from all Drawers."""
        stats = {}
        for node_id, node in self._nodes.items():
            if node.drawer:
                stats[node_id] = node.drawer.get_statistics()
        return stats

    def get_hiatus_statistics(self) -> Dict[str, Dict]:
        """Get statistics from all Hiatus controllers."""
        stats = {}
        for hiatus_id in self.hiatus_ids:
            node = self._nodes.get(hiatus_id)
            if node and node.hiatus_controller:
                stats[hiatus_id] = node.hiatus_controller.get_statistics()
        return stats

    def reset(self) -> None:
        """Reset all router state."""
        self.stats.reset()
        for node in self._nodes.values():
            if node.drawer:
                node.drawer.reset()
            if node.hiatus_controller:
                node.hiatus_controller.reset()


def initialize_distributed_router(graph: NetworkGraph,
                                   config: Optional[DistributedConfig] = None) -> DistributedSRSDRouter:
    """
    Factory function to create a properly initialized DistributedSRSDRouter.

    Args:
        graph: NetworkGraph instance
        config: Optional configuration

    Returns:
        Initialized DistributedSRSDRouter
    """
    return DistributedSRSDRouter(graph, config)
