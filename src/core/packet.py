"""
Packet - Onion-structured packet for SRSD routing.

Packets contain encrypted layers that hide the true origin and destination.
Only the current segment destination is visible at any routing point.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import time
import uuid


@dataclass
class EncryptedLayer:
    """
    A single encrypted layer of the onion packet.

    Each layer contains:
    - segment_destination: The destination for this routing segment
    - is_final: Whether this is the final destination
    """

    segment_destination: str
    is_final: bool = False

    # In a real implementation, this would include:
    # - Encrypted payload for the next layer
    # - Cryptographic overhead (MACs, nonces, etc.)
    # - Session keys


@dataclass
class NextHopInfo:
    """
    Information extracted from peeling an onion layer.

    This is what a Hiatus node learns after decryption.
    """

    segment_destination: str
    is_final: bool
    added_delay: float = 0.0


@dataclass
class Packet:
    """
    Onion-encrypted packet for SRSD routing.

    Security properties:
    - Origin is NOT visible (hidden in innermost layer)
    - Final destination is NOT visible (encrypted until final Hiatus)
    - Only current segment destination is visible
    - Intermediate nodes cannot correlate entry/exit

    Structure:
    - layers: Stack of encrypted layers, outer to inner
    - current_layer: Index of the next layer to peel
    """

    packet_id: str
    layers: List[EncryptedLayer]
    current_layer: int = 0
    timestamp: float = field(default_factory=time.time)

    # Metadata (NOT visible to intermediate nodes in real implementation)
    # These are for simulation/analysis only
    _true_source: Optional[str] = field(default=None, repr=False)
    _true_destination: Optional[str] = field(default=None, repr=False)
    _creation_time: float = field(default_factory=time.time, repr=False)
    _total_delay: float = field(default=0.0, repr=False)

    def peel_layer(self) -> Optional[NextHopInfo]:
        """
        Peel (decrypt) the current outer layer to reveal the next destination.

        In onion routing, peeling reveals where to go NEXT, not the current
        destination. After peeling at node H1, we learn to go to H2.

        Returns the information about the NEXT segment:
        - Next segment destination
        - Whether this is the final destination

        Returns None if no more layers to peel.
        """
        # Increment first to move to the next layer
        self.current_layer += 1

        if self.current_layer >= len(self.layers):
            return None

        layer = self.layers[self.current_layer]

        return NextHopInfo(
            segment_destination=layer.segment_destination,
            is_final=layer.is_final
        )

    def peek_layer(self) -> Optional[EncryptedLayer]:
        """
        Peek at the current layer without peeling it.

        Used by routers to see the segment destination.
        """
        if self.current_layer >= len(self.layers):
            return None
        return self.layers[self.current_layer]

    def get_current_segment_destination(self) -> Optional[str]:
        """
        Get the current visible segment destination.

        This is the only routing information visible to the current node.
        """
        layer = self.peek_layer()
        if layer is None:
            return None
        return layer.segment_destination

    def is_at_final_destination(self) -> bool:
        """Check if packet has reached its final destination."""
        layer = self.peek_layer()
        if layer is None:
            return True
        return layer.is_final and self.current_layer == len(self.layers) - 1

    def add_delay(self, delay: float) -> None:
        """Add delay to packet (for mixing simulation)."""
        self._total_delay += delay

    @property
    def remaining_layers(self) -> int:
        """Number of layers yet to be peeled."""
        return len(self.layers) - self.current_layer

    @property
    def total_layers(self) -> int:
        """Total number of layers in the packet."""
        return len(self.layers)

    def to_dict(self) -> dict:
        """Serialize packet to dictionary (for logging/debugging)."""
        return {
            'packet_id': self.packet_id,
            'current_layer': self.current_layer,
            'total_layers': len(self.layers),
            'remaining_layers': self.remaining_layers,
            'timestamp': self.timestamp,
            'total_delay': self._total_delay,
        }


def create_onion_packet(packet_id: str,
                        hiatus_sequence: List[str],
                        final_destination: str,
                        source: Optional[str] = None) -> Packet:
    """
    Create an onion packet for SRSD routing.

    The packet structure is:
    - Layer 0: First Hiatus (segment 1 destination)
    - Layer 1: Second Hiatus (segment 2 destination)
    - ...
    - Layer N: Final destination (is_final=True)

    Args:
        packet_id: Unique packet identifier
        hiatus_sequence: List of Hiatus node IDs in order
        final_destination: The true final destination
        source: Optional source for metadata (not visible in packet)

    Returns:
        Onion-encrypted Packet
    """
    layers = []

    # Add layer for each Hiatus
    for hiatus_id in hiatus_sequence:
        layers.append(EncryptedLayer(
            segment_destination=hiatus_id,
            is_final=False
        ))

    # Add final layer for destination
    layers.append(EncryptedLayer(
        segment_destination=final_destination,
        is_final=True
    ))

    return Packet(
        packet_id=packet_id,
        layers=layers,
        _true_source=source,
        _true_destination=final_destination
    )


def generate_packet_id() -> str:
    """Generate a unique packet ID."""
    return f"pkt_{uuid.uuid4().hex[:12]}"


@dataclass
class ForwardingTrace:
    """
    Trace of a packet's forwarding path.

    Used for simulation analysis only - not visible to network nodes.
    """

    hops: List[tuple] = field(default_factory=list)  # List of (from, to) tuples
    timestamps: List[float] = field(default_factory=list)
    delays: List[float] = field(default_factory=list)
    reached_destination: bool = False
    dropped: bool = False
    drop_reason: Optional[str] = None

    def add_hop(self, from_node: str, to_node: str,
                timestamp: Optional[float] = None,
                delay: float = 0.0) -> None:
        """Record a forwarding hop."""
        self.hops.append((from_node, to_node))
        self.timestamps.append(timestamp or time.time())
        self.delays.append(delay)

    @property
    def path(self) -> List[str]:
        """Get the path as a list of node IDs."""
        if not self.hops:
            return []

        path = [self.hops[0][0]]  # Start with first source
        for _, to_node in self.hops:
            path.append(to_node)
        return path

    @property
    def hop_count(self) -> int:
        """Number of hops in the trace."""
        return len(self.hops)

    @property
    def total_delay(self) -> float:
        """Total delay accumulated."""
        return sum(self.delays)

    def mark_reached(self) -> None:
        """Mark that the packet reached its destination."""
        self.reached_destination = True

    def mark_dropped(self, reason: str = "unknown") -> None:
        """Mark that the packet was dropped."""
        self.dropped = True
        self.drop_reason = reason

    def to_dict(self) -> dict:
        """Serialize trace to dictionary."""
        return {
            'path': self.path,
            'hop_count': self.hop_count,
            'total_delay': self.total_delay,
            'reached_destination': self.reached_destination,
            'dropped': self.dropped,
            'drop_reason': self.drop_reason,
        }
