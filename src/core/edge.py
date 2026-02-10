"""
Edge module - Logical paths with structural attributes.

Edges represent connections between nodes with attributes relevant to
structural analysis and routing decisions.
"""

from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class EdgeAttributes:
    """Structural attributes of an edge."""

    recurrence: float = 0.0  # How often this edge is reused (0-1)
    exposure: float = 0.0    # Structural exposure level (0-1)
    weight: float = 1.0      # Structural weight (not optimal cost)
    latency: float = 1.0     # Base latency in milliseconds
    bandwidth: float = 1000.0  # Bandwidth in Mbps

    # QKD-related attributes
    qkd_enabled: bool = False
    qkd_key_rate: float = 0.0  # Key generation rate (bits/s)
    qkd_error_rate: float = 0.0  # Quantum bit error rate (QBER)

    def structural_score(self) -> float:
        """
        Calculate a combined structural score.
        Lower is better (less exposed, less recurrent).
        """
        return (self.recurrence * 0.5 + self.exposure * 0.5) * self.weight


@dataclass
class Edge:
    """
    Represents a directed edge between two nodes.

    Tracks structural attributes for routing decisions and
    maintains usage statistics for adversary analysis.
    """

    source: str
    target: str
    attributes: EdgeAttributes = field(default_factory=EdgeAttributes)

    # Usage tracking
    usage_count: int = 0
    last_used: Optional[float] = None
    usage_history: list = field(default_factory=list)

    @property
    def id(self) -> str:
        """Unique identifier for this edge."""
        return f"{self.source}->{self.target}"

    def record_usage(self, timestamp: Optional[float] = None) -> None:
        """Record that this edge was used for routing."""
        ts = timestamp or time.time()
        self.usage_count += 1
        self.last_used = ts
        self.usage_history.append(ts)

        # Update recurrence based on usage pattern
        self._update_recurrence()

    def _update_recurrence(self, window_size: int = 100) -> None:
        """Update recurrence score based on recent usage."""
        if len(self.usage_history) < 2:
            return

        # Calculate recurrence as frequency in recent window
        recent = self.usage_history[-window_size:]
        if len(recent) > 1:
            time_span = recent[-1] - recent[0]
            if time_span > 0:
                frequency = len(recent) / time_span
                # Normalize to 0-1 range (assuming max 10 uses per second)
                self.attributes.recurrence = min(1.0, frequency / 10.0)

    def reset_usage(self) -> None:
        """Reset usage statistics."""
        self.usage_count = 0
        self.last_used = None
        self.usage_history = []
        self.attributes.recurrence = 0.0

    def get_effective_weight(self,
                             recurrence_penalty: float = 1.0,
                             exposure_penalty: float = 1.0) -> float:
        """
        Calculate effective weight considering penalties.

        Args:
            recurrence_penalty: Multiplier for recurrence impact
            exposure_penalty: Multiplier for exposure impact

        Returns:
            Effective weight for routing decisions
        """
        base = self.attributes.weight
        recurrence_cost = self.attributes.recurrence * recurrence_penalty
        exposure_cost = self.attributes.exposure * exposure_penalty

        return base * (1 + recurrence_cost + exposure_cost)

    def to_dict(self) -> dict:
        """Serialize edge to dictionary."""
        return {
            'source': self.source,
            'target': self.target,
            'attributes': {
                'recurrence': self.attributes.recurrence,
                'exposure': self.attributes.exposure,
                'weight': self.attributes.weight,
                'latency': self.attributes.latency,
                'bandwidth': self.attributes.bandwidth,
                'qkd_enabled': self.attributes.qkd_enabled,
                'qkd_key_rate': self.attributes.qkd_key_rate,
                'qkd_error_rate': self.attributes.qkd_error_rate,
            },
            'usage_count': self.usage_count,
            'last_used': self.last_used,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Edge':
        """Deserialize edge from dictionary."""
        attrs = EdgeAttributes(**data.get('attributes', {}))
        edge = cls(
            source=data['source'],
            target=data['target'],
            attributes=attrs,
        )
        edge.usage_count = data.get('usage_count', 0)
        edge.last_used = data.get('last_used')
        return edge
