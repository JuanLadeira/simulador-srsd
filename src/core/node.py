"""
Node module - Forwarding entities in the network.

Nodes represent routers/switches that forward traffic and maintain
local state for routing decisions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Set
import time

if TYPE_CHECKING:
    from .drawer import Drawer
    from .hiatus import HiatusController


class NodeType(Enum):
    """Types of network nodes."""
    ENDPOINT = "endpoint"       # Source/destination nodes
    ROUTER = "router"           # Standard forwarding node
    HIATUS = "hiatus"           # CAR - structural discontinuity point
    QKD_ENABLED = "qkd_enabled"  # Node with QKD capability


class NodeState(Enum):
    """Operational state of a node."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class NodeStatistics:
    """Traffic and routing statistics for a node."""

    packets_forwarded: int = 0
    packets_dropped: int = 0
    bytes_forwarded: int = 0
    routing_decisions: int = 0
    last_activity: Optional[float] = None

    # Flow tracking
    flows_seen: Set[str] = field(default_factory=set)
    flow_entry_times: Dict[str, List[float]] = field(default_factory=dict)
    flow_exit_times: Dict[str, List[float]] = field(default_factory=dict)

    def record_forward(self, packet_size: int = 64) -> None:
        """Record a packet forwarding event."""
        self.packets_forwarded += 1
        self.bytes_forwarded += packet_size
        self.last_activity = time.time()

    def record_drop(self) -> None:
        """Record a packet drop event."""
        self.packets_dropped += 1
        self.last_activity = time.time()

    def record_flow_entry(self, flow_id: str, timestamp: Optional[float] = None) -> None:
        """Record when a flow enters this node."""
        ts = timestamp or time.time()
        self.flows_seen.add(flow_id)
        if flow_id not in self.flow_entry_times:
            self.flow_entry_times[flow_id] = []
        self.flow_entry_times[flow_id].append(ts)

    def record_flow_exit(self, flow_id: str, timestamp: Optional[float] = None) -> None:
        """Record when a flow exits this node."""
        ts = timestamp or time.time()
        if flow_id not in self.flow_exit_times:
            self.flow_exit_times[flow_id] = []
        self.flow_exit_times[flow_id].append(ts)

    def reset(self) -> None:
        """Reset all statistics."""
        self.packets_forwarded = 0
        self.packets_dropped = 0
        self.bytes_forwarded = 0
        self.routing_decisions = 0
        self.last_activity = None
        self.flows_seen = set()
        self.flow_entry_times = {}
        self.flow_exit_times = {}


@dataclass
class Node:
    """
    Represents a network node (router/switch).

    Maintains state for routing decisions and tracks traffic patterns
    for analysis.
    """

    id: str
    node_type: NodeType = NodeType.ROUTER
    state: NodeState = NodeState.ACTIVE

    # Position (for visualization)
    x: float = 0.0
    y: float = 0.0

    # Neighbors (edge references)
    outgoing_edges: List[str] = field(default_factory=list)
    incoming_edges: List[str] = field(default_factory=list)

    # Statistics
    stats: NodeStatistics = field(default_factory=NodeStatistics)

    # QKD-specific attributes
    qkd_key_pool: float = 0.0  # Available key material (bits)
    qkd_generation_rate: float = 0.0  # Key generation rate (bits/s)

    # Local routing state
    routing_table: Dict[str, str] = field(default_factory=dict)

    # SRSD components (initialized separately)
    drawer: Optional['Drawer'] = None
    hiatus_controller: Optional['HiatusController'] = None

    def is_active(self) -> bool:
        """Check if node is operational."""
        return self.state == NodeState.ACTIVE

    def is_qkd_capable(self) -> bool:
        """Check if node has QKD capability."""
        return self.node_type == NodeType.QKD_ENABLED

    def is_hiatus(self) -> bool:
        """Check if node is a Hiatus (CAR) point."""
        return self.node_type == NodeType.HIATUS

    def initialize_drawer(self, neighbors: List[str],
                          blocking_window: int = 3,
                          seed: Optional[int] = None) -> None:
        """
        Initialize the Drawer for this node.

        Args:
            neighbors: List of direct neighbor node IDs
            blocking_window: Number of selections before automatic unblock
            seed: Random seed for reproducibility
        """
        from .drawer import Drawer
        self.drawer = Drawer(self.id, neighbors, blocking_window, seed)

    def initialize_hiatus_controller(self,
                                      mixing_delay_mean: float = 0.01,
                                      mixing_delay_std: float = 0.005,
                                      seed: Optional[int] = None) -> None:
        """
        Initialize the HiatusController for this node.

        Only meaningful if node_type is HIATUS.

        Args:
            mixing_delay_mean: Mean mixing delay in seconds
            mixing_delay_std: Standard deviation of mixing delay
            seed: Random seed for reproducibility
        """
        from .hiatus import HiatusController
        self.hiatus_controller = HiatusController(
            self.id, mixing_delay_mean, mixing_delay_std, seed
        )

    def add_outgoing_edge(self, edge_id: str) -> None:
        """Register an outgoing edge."""
        if edge_id not in self.outgoing_edges:
            self.outgoing_edges.append(edge_id)

    def add_incoming_edge(self, edge_id: str) -> None:
        """Register an incoming edge."""
        if edge_id not in self.incoming_edges:
            self.incoming_edges.append(edge_id)

    def remove_outgoing_edge(self, edge_id: str) -> None:
        """Remove an outgoing edge."""
        if edge_id in self.outgoing_edges:
            self.outgoing_edges.remove(edge_id)

    def remove_incoming_edge(self, edge_id: str) -> None:
        """Remove an incoming edge."""
        if edge_id in self.incoming_edges:
            self.incoming_edges.remove(edge_id)

    def get_neighbors(self) -> List[str]:
        """Get list of neighbor node IDs from outgoing edges."""
        # Edge IDs are in format "source->target"
        neighbors = []
        for edge_id in self.outgoing_edges:
            if '->' in edge_id:
                target = edge_id.split('->')[1]
                neighbors.append(target)
        return neighbors

    def forward_packet(self, flow_id: str, packet_size: int = 64,
                       timestamp: Optional[float] = None) -> None:
        """Record packet forwarding through this node."""
        self.stats.record_forward(packet_size)
        self.stats.record_flow_entry(flow_id, timestamp)

    def set_routing_entry(self, destination: str, next_hop: str) -> None:
        """Set routing table entry."""
        self.routing_table[destination] = next_hop
        self.stats.routing_decisions += 1

    def get_next_hop(self, destination: str) -> Optional[str]:
        """Get next hop for a destination."""
        return self.routing_table.get(destination)

    def update_qkd_keys(self, delta_time: float) -> None:
        """Update QKD key pool based on generation rate."""
        if self.is_qkd_capable():
            self.qkd_key_pool += self.qkd_generation_rate * delta_time

    def consume_qkd_keys(self, amount: float) -> bool:
        """
        Consume QKD keys for encryption.

        Returns True if sufficient keys available, False otherwise.
        """
        if self.qkd_key_pool >= amount:
            self.qkd_key_pool -= amount
            return True
        return False

    def to_dict(self) -> dict:
        """Serialize node to dictionary."""
        return {
            'id': self.id,
            'node_type': self.node_type.value,
            'state': self.state.value,
            'x': self.x,
            'y': self.y,
            'outgoing_edges': self.outgoing_edges.copy(),
            'incoming_edges': self.incoming_edges.copy(),
            'stats': {
                'packets_forwarded': self.stats.packets_forwarded,
                'packets_dropped': self.stats.packets_dropped,
                'bytes_forwarded': self.stats.bytes_forwarded,
                'routing_decisions': self.stats.routing_decisions,
            },
            'qkd_key_pool': self.qkd_key_pool,
            'qkd_generation_rate': self.qkd_generation_rate,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Node':
        """Deserialize node from dictionary."""
        node = cls(
            id=data['id'],
            node_type=NodeType(data.get('node_type', 'router')),
            state=NodeState(data.get('state', 'active')),
            x=data.get('x', 0.0),
            y=data.get('y', 0.0),
        )
        node.outgoing_edges = data.get('outgoing_edges', [])
        node.incoming_edges = data.get('incoming_edges', [])
        node.qkd_key_pool = data.get('qkd_key_pool', 0.0)
        node.qkd_generation_rate = data.get('qkd_generation_rate', 0.0)

        if 'stats' in data:
            node.stats.packets_forwarded = data['stats'].get('packets_forwarded', 0)
            node.stats.packets_dropped = data['stats'].get('packets_dropped', 0)
            node.stats.bytes_forwarded = data['stats'].get('bytes_forwarded', 0)
            node.stats.routing_decisions = data['stats'].get('routing_decisions', 0)

        return node
