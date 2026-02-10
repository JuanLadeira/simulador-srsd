"""
QKD Channel - Quantum Key Distribution channel abstraction.

Provides an abstraction layer for QKD channels that can be used
by SRSD for routing decisions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import time
import random
import math


class ChannelState(Enum):
    """State of a QKD channel."""
    ACTIVE = "active"           # Fully operational
    DEGRADED = "degraded"       # Operating with reduced performance
    INTERRUPTED = "interrupted"  # Temporarily unavailable
    FAILED = "failed"           # Channel failure


@dataclass
class ChannelMetrics:
    """Real-time metrics for a QKD channel."""

    # Key generation
    key_rate: float = 0.0           # Secure key rate (bits/s)
    raw_key_rate: float = 0.0       # Raw key rate before privacy amplification

    # Error metrics
    qber: float = 0.0               # Quantum Bit Error Rate (0-1)
    classical_ber: float = 0.0      # Classical channel BER

    # Availability
    uptime_ratio: float = 1.0       # Uptime in recent window (0-1)
    last_key_generation: Optional[float] = None

    # Key pool
    available_keys: float = 0.0     # Available key material (bits)
    key_consumption_rate: float = 0.0  # Key usage rate (bits/s)

    def get_effective_rate(self) -> float:
        """Get effective secure key rate considering QBER."""
        if self.qber >= 0.11:  # BB84 security threshold
            return 0.0
        # Simplified key rate calculation
        return self.key_rate * (1 - 2 * self.qber)

    def is_secure(self) -> bool:
        """Check if channel is within secure operating parameters."""
        return self.qber < 0.11 and self.uptime_ratio > 0.5


@dataclass
class QKDChannel:
    """
    Represents a QKD channel between two nodes.

    Provides metrics and state for routing decisions.
    """

    source: str
    target: str
    state: ChannelState = ChannelState.ACTIVE
    metrics: ChannelMetrics = field(default_factory=ChannelMetrics)

    # Configuration
    max_distance: float = 100.0     # Maximum distance in km
    distance: float = 0.0           # Actual distance
    fiber_loss: float = 0.2         # Loss in dB/km

    # State history
    state_history: List[Tuple[float, ChannelState]] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Unique identifier for this channel."""
        return f"qkd_{self.source}->{self.target}"

    def update_metrics(self, qber: Optional[float] = None,
                       key_rate: Optional[float] = None) -> None:
        """Update channel metrics."""
        if qber is not None:
            self.metrics.qber = qber
            self._check_security_threshold()

        if key_rate is not None:
            self.metrics.key_rate = key_rate
            self.metrics.last_key_generation = time.time()

    def _check_security_threshold(self) -> None:
        """Check if QBER exceeds security threshold."""
        if self.metrics.qber >= 0.11:
            self.set_state(ChannelState.INTERRUPTED)
        elif self.metrics.qber >= 0.05:
            self.set_state(ChannelState.DEGRADED)
        elif self.state != ChannelState.FAILED:
            self.set_state(ChannelState.ACTIVE)

    def set_state(self, new_state: ChannelState) -> None:
        """Set channel state and record history."""
        if new_state != self.state:
            self.state_history.append((time.time(), self.state))
            self.state = new_state

    def generate_keys(self, duration: float) -> float:
        """
        Simulate key generation over a duration.

        Args:
            duration: Time period in seconds

        Returns:
            Amount of key material generated (bits)
        """
        if self.state in (ChannelState.INTERRUPTED, ChannelState.FAILED):
            return 0.0

        effective_rate = self.metrics.get_effective_rate()
        generated = effective_rate * duration

        self.metrics.available_keys += generated
        return generated

    def consume_keys(self, amount: float) -> bool:
        """
        Consume key material for encryption.

        Args:
            amount: Amount of key material needed (bits)

        Returns:
            True if sufficient keys available
        """
        if self.metrics.available_keys >= amount:
            self.metrics.available_keys -= amount
            self.metrics.key_consumption_rate = amount  # Simplified tracking
            return True
        return False

    def get_risk_level(self) -> float:
        """
        Calculate risk level for this channel (0-1).

        Higher risk = less desirable for routing.
        """
        risk = 0.0

        # QBER contribution (higher QBER = higher risk)
        risk += min(1.0, self.metrics.qber / 0.11) * 0.4

        # State contribution
        state_risk = {
            ChannelState.ACTIVE: 0.0,
            ChannelState.DEGRADED: 0.3,
            ChannelState.INTERRUPTED: 0.8,
            ChannelState.FAILED: 1.0,
        }
        risk += state_risk.get(self.state, 0.5) * 0.4

        # Availability contribution
        risk += (1 - self.metrics.uptime_ratio) * 0.2

        return min(1.0, risk)

    def is_operational(self) -> bool:
        """Check if channel is operational."""
        return self.state in (ChannelState.ACTIVE, ChannelState.DEGRADED)

    def to_dict(self) -> dict:
        """Serialize channel to dictionary."""
        return {
            'source': self.source,
            'target': self.target,
            'state': self.state.value,
            'distance': self.distance,
            'metrics': {
                'key_rate': self.metrics.key_rate,
                'qber': self.metrics.qber,
                'available_keys': self.metrics.available_keys,
                'uptime_ratio': self.metrics.uptime_ratio,
            },
        }


class QKDChannelManager:
    """
    Manages multiple QKD channels in the network.

    Provides centralized access to channel state and metrics
    for routing decisions.
    """

    def __init__(self):
        """Initialize channel manager."""
        self._channels: Dict[str, QKDChannel] = {}
        self._node_channels: Dict[str, List[str]] = {}

    def add_channel(self, channel: QKDChannel) -> None:
        """Add a QKD channel to the manager."""
        self._channels[channel.id] = channel

        # Track channels by node
        if channel.source not in self._node_channels:
            self._node_channels[channel.source] = []
        if channel.target not in self._node_channels:
            self._node_channels[channel.target] = []

        self._node_channels[channel.source].append(channel.id)
        self._node_channels[channel.target].append(channel.id)

    def create_channel(self, source: str, target: str,
                       distance: float = 10.0,
                       initial_qber: float = 0.01,
                       initial_key_rate: float = 1000.0) -> QKDChannel:
        """
        Create and add a new QKD channel.

        Args:
            source: Source node ID
            target: Target node ID
            distance: Channel distance in km
            initial_qber: Initial QBER
            initial_key_rate: Initial key rate (bits/s)

        Returns:
            Created channel
        """
        metrics = ChannelMetrics(
            key_rate=initial_key_rate,
            qber=initial_qber,
        )

        channel = QKDChannel(
            source=source,
            target=target,
            distance=distance,
            metrics=metrics,
        )

        self.add_channel(channel)
        return channel

    def get_channel(self, source: str, target: str) -> Optional[QKDChannel]:
        """Get channel between two nodes."""
        channel_id = f"qkd_{source}->{target}"
        return self._channels.get(channel_id)

    def get_channel_risk(self, source: str, target: str) -> float:
        """
        Get risk level for a channel.

        Returns 1.0 (maximum risk) if no QKD channel exists.
        """
        channel = self.get_channel(source, target)
        if channel is None:
            return 1.0
        return channel.get_risk_level()

    def get_node_channels(self, node_id: str) -> List[QKDChannel]:
        """Get all channels connected to a node."""
        channel_ids = self._node_channels.get(node_id, [])
        return [self._channels[cid] for cid in channel_ids if cid in self._channels]

    def get_all_channels(self) -> List[QKDChannel]:
        """Get all channels."""
        return list(self._channels.values())

    def get_operational_channels(self) -> List[QKDChannel]:
        """Get all operational channels."""
        return [c for c in self._channels.values() if c.is_operational()]

    def simulate_step(self, duration: float) -> Dict[str, float]:
        """
        Simulate one time step for all channels.

        Args:
            duration: Time step duration in seconds

        Returns:
            Dictionary of channel ID to generated keys
        """
        generated = {}
        for channel_id, channel in self._channels.items():
            keys = channel.generate_keys(duration)
            generated[channel_id] = keys
        return generated

    def apply_noise(self, noise_level: float = 0.01,
                    seed: Optional[int] = None) -> None:
        """
        Apply random noise to channel metrics.

        Simulates real-world variations in QKD performance.

        Args:
            noise_level: Standard deviation of noise
            seed: Random seed for reproducibility
        """
        rng = random.Random(seed)

        for channel in self._channels.values():
            # Add noise to QBER
            noise = rng.gauss(0, noise_level)
            new_qber = max(0, min(0.5, channel.metrics.qber + noise))
            channel.update_metrics(qber=new_qber)

            # Add noise to key rate
            rate_noise = rng.gauss(0, noise_level * channel.metrics.key_rate)
            new_rate = max(0, channel.metrics.key_rate + rate_noise)
            channel.update_metrics(key_rate=new_rate)

    def get_network_statistics(self) -> Dict:
        """Get network-wide QKD statistics."""
        channels = self.get_all_channels()
        if not channels:
            return {
                'total_channels': 0,
                'operational_channels': 0,
                'avg_qber': 0.0,
                'avg_risk': 0.0,
            }

        operational = [c for c in channels if c.is_operational()]
        qbers = [c.metrics.qber for c in channels]
        risks = [c.get_risk_level() for c in channels]

        return {
            'total_channels': len(channels),
            'operational_channels': len(operational),
            'operational_ratio': len(operational) / len(channels),
            'avg_qber': sum(qbers) / len(qbers),
            'max_qber': max(qbers),
            'min_qber': min(qbers),
            'avg_risk': sum(risks) / len(risks),
            'total_available_keys': sum(c.metrics.available_keys for c in channels),
        }

    def reset(self) -> None:
        """Reset all channels to initial state."""
        for channel in self._channels.values():
            channel.state = ChannelState.ACTIVE
            channel.metrics.available_keys = 0
            channel.state_history.clear()
