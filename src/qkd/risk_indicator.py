"""
QKD Risk Indicators - Risk assessment for QKD-based routing.

Provides risk metrics that can be used by SRSD to make
routing decisions that favor more secure channels.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple
import time
import math

from .channel import QKDChannel, QKDChannelManager, ChannelState


class RiskLevel(Enum):
    """Discrete risk levels for simplicity."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskIndicator:
    """
    Risk indicator for a network path or edge.

    Combines multiple risk factors into a single metric.
    """

    # Core metrics
    qkd_risk: float = 0.0           # QKD channel risk (0-1)
    structural_risk: float = 0.0    # Structural exposure risk (0-1)
    temporal_risk: float = 0.0      # Time-based risk (0-1)

    # Weights
    qkd_weight: float = 0.5
    structural_weight: float = 0.3
    temporal_weight: float = 0.2

    # Thresholds
    low_threshold: float = 0.3
    medium_threshold: float = 0.5
    high_threshold: float = 0.7

    @property
    def combined_risk(self) -> float:
        """Calculate combined weighted risk."""
        return (
            self.qkd_risk * self.qkd_weight +
            self.structural_risk * self.structural_weight +
            self.temporal_risk * self.temporal_weight
        )

    @property
    def risk_level(self) -> RiskLevel:
        """Get discrete risk level."""
        risk = self.combined_risk
        if risk < self.low_threshold:
            return RiskLevel.LOW
        elif risk < self.medium_threshold:
            return RiskLevel.MEDIUM
        elif risk < self.high_threshold:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'qkd_risk': self.qkd_risk,
            'structural_risk': self.structural_risk,
            'temporal_risk': self.temporal_risk,
            'combined_risk': self.combined_risk,
            'risk_level': self.risk_level.value,
        }


class RiskAssessor:
    """
    Assesses risk for network paths and edges.

    Integrates QKD channel state with structural analysis
    to provide comprehensive risk indicators.
    """

    def __init__(self, channel_manager: Optional[QKDChannelManager] = None):
        """
        Initialize risk assessor.

        Args:
            channel_manager: QKD channel manager for channel metrics
        """
        self.channel_manager = channel_manager

        # Edge risk cache
        self._edge_risks: Dict[str, RiskIndicator] = {}

        # Historical data for temporal risk
        self._edge_history: Dict[str, List[Tuple[float, float]]] = {}

        # Configuration
        self.config = {
            'qkd_weight': 0.5,
            'structural_weight': 0.3,
            'temporal_weight': 0.2,
            'history_window': 3600.0,  # 1 hour
        }

    def assess_edge(self, source: str, target: str,
                    structural_exposure: float = 0.0,
                    recurrence: float = 0.0) -> RiskIndicator:
        """
        Assess risk for a single edge.

        Args:
            source: Source node ID
            target: Target node ID
            structural_exposure: Exposure level from structural analysis
            recurrence: Recurrence level from route memory

        Returns:
            Risk indicator for the edge
        """
        edge_id = f"{source}->{target}"

        # QKD risk
        qkd_risk = self._assess_qkd_risk(source, target)

        # Structural risk (exposure + recurrence)
        structural_risk = (structural_exposure * 0.6 + recurrence * 0.4)

        # Temporal risk (based on history)
        temporal_risk = self._assess_temporal_risk(edge_id)

        indicator = RiskIndicator(
            qkd_risk=qkd_risk,
            structural_risk=structural_risk,
            temporal_risk=temporal_risk,
            qkd_weight=self.config['qkd_weight'],
            structural_weight=self.config['structural_weight'],
            temporal_weight=self.config['temporal_weight'],
        )

        # Cache the result
        self._edge_risks[edge_id] = indicator

        return indicator

    def assess_path(self, path: List[str],
                    edge_exposures: Optional[Dict[str, float]] = None,
                    edge_recurrences: Optional[Dict[str, float]] = None) -> RiskIndicator:
        """
        Assess risk for a complete path.

        Aggregates edge risks along the path.

        Args:
            path: List of node IDs in the path
            edge_exposures: Optional exposure values per edge
            edge_recurrences: Optional recurrence values per edge

        Returns:
            Aggregated risk indicator for the path
        """
        if len(path) < 2:
            return RiskIndicator()

        edge_exposures = edge_exposures or {}
        edge_recurrences = edge_recurrences or {}

        qkd_risks = []
        structural_risks = []
        temporal_risks = []

        for i in range(len(path) - 1):
            source, target = path[i], path[i + 1]
            edge_id = f"{source}->{target}"

            exposure = edge_exposures.get(edge_id, 0.0)
            recurrence = edge_recurrences.get(edge_id, 0.0)

            indicator = self.assess_edge(source, target, exposure, recurrence)

            qkd_risks.append(indicator.qkd_risk)
            structural_risks.append(indicator.structural_risk)
            temporal_risks.append(indicator.temporal_risk)

        # Aggregate using max (weakest link)
        return RiskIndicator(
            qkd_risk=max(qkd_risks) if qkd_risks else 0.0,
            structural_risk=max(structural_risks) if structural_risks else 0.0,
            temporal_risk=max(temporal_risks) if temporal_risks else 0.0,
            qkd_weight=self.config['qkd_weight'],
            structural_weight=self.config['structural_weight'],
            temporal_weight=self.config['temporal_weight'],
        )

    def _assess_qkd_risk(self, source: str, target: str) -> float:
        """Assess QKD-specific risk for an edge."""
        if self.channel_manager is None:
            return 0.5  # Unknown risk

        channel = self.channel_manager.get_channel(source, target)
        if channel is None:
            return 1.0  # No QKD = maximum QKD risk

        return channel.get_risk_level()

    def _assess_temporal_risk(self, edge_id: str) -> float:
        """Assess time-based risk (e.g., recent attacks, anomalies)."""
        if edge_id not in self._edge_history:
            return 0.0

        now = time.time()
        window = self.config['history_window']
        cutoff = now - window

        # Get recent risk events
        recent = [
            (ts, risk) for ts, risk in self._edge_history[edge_id]
            if ts > cutoff
        ]

        if not recent:
            return 0.0

        # Weight recent events more heavily
        weighted_sum = 0.0
        weight_sum = 0.0
        for ts, risk in recent:
            age = now - ts
            weight = math.exp(-age / (window / 2))  # Exponential decay
            weighted_sum += risk * weight
            weight_sum += weight

        return weighted_sum / weight_sum if weight_sum > 0 else 0.0

    def record_risk_event(self, source: str, target: str,
                          risk_level: float,
                          timestamp: Optional[float] = None) -> None:
        """
        Record a risk event for temporal analysis.

        Args:
            source: Source node
            target: Target node
            risk_level: Risk level (0-1)
            timestamp: Optional timestamp
        """
        edge_id = f"{source}->{target}"
        ts = timestamp or time.time()

        if edge_id not in self._edge_history:
            self._edge_history[edge_id] = []

        self._edge_history[edge_id].append((ts, risk_level))

        # Cleanup old entries
        self._cleanup_history(edge_id)

    def _cleanup_history(self, edge_id: str) -> None:
        """Remove old entries from history."""
        window = self.config['history_window']
        cutoff = time.time() - window * 2

        self._edge_history[edge_id] = [
            (ts, risk) for ts, risk in self._edge_history[edge_id]
            if ts > cutoff
        ]

    def get_safest_path(self, paths: List[List[str]]) -> Optional[List[str]]:
        """
        Select the safest path from a list of candidates.

        Args:
            paths: List of candidate paths

        Returns:
            Path with lowest combined risk
        """
        if not paths:
            return None

        path_risks = []
        for path in paths:
            indicator = self.assess_path(path)
            path_risks.append((path, indicator.combined_risk))

        # Sort by risk (ascending)
        path_risks.sort(key=lambda x: x[1])

        return path_risks[0][0]

    def get_risk_summary(self) -> Dict:
        """Get summary of current risk assessments."""
        if not self._edge_risks:
            return {
                'total_edges': 0,
                'avg_risk': 0.0,
                'high_risk_edges': 0,
            }

        risks = [ind.combined_risk for ind in self._edge_risks.values()]
        high_risk = sum(1 for r in risks if r > 0.7)

        return {
            'total_edges': len(self._edge_risks),
            'avg_risk': sum(risks) / len(risks),
            'max_risk': max(risks),
            'min_risk': min(risks),
            'high_risk_edges': high_risk,
            'risk_distribution': {
                'low': sum(1 for r in risks if r < 0.3),
                'medium': sum(1 for r in risks if 0.3 <= r < 0.5),
                'high': sum(1 for r in risks if 0.5 <= r < 0.7),
                'critical': sum(1 for r in risks if r >= 0.7),
            },
        }

    def reset(self) -> None:
        """Reset all cached data."""
        self._edge_risks.clear()
        self._edge_history.clear()


class AdaptiveRiskThreshold:
    """
    Adaptive risk threshold that adjusts based on network conditions.

    Allows SRSD to be more or less aggressive about risk avoidance
    depending on overall network state.
    """

    def __init__(self,
                 base_threshold: float = 0.5,
                 min_threshold: float = 0.2,
                 max_threshold: float = 0.9,
                 adaptation_rate: float = 0.1):
        """
        Initialize adaptive threshold.

        Args:
            base_threshold: Starting threshold
            min_threshold: Minimum allowed threshold
            max_threshold: Maximum allowed threshold
            adaptation_rate: How fast to adapt
        """
        self.base_threshold = base_threshold
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.adaptation_rate = adaptation_rate

        self._current_threshold = base_threshold
        self._history: List[Tuple[float, float]] = []

    @property
    def current(self) -> float:
        """Get current threshold."""
        return self._current_threshold

    def update(self, network_risk: float, available_paths: int) -> None:
        """
        Update threshold based on current conditions.

        Args:
            network_risk: Average risk level in network
            available_paths: Number of available path alternatives
        """
        # If few paths available, need to be more lenient
        path_factor = min(1.0, available_paths / 5)

        # If network is generally risky, raise threshold (accept more risk)
        # If network is safe, lower threshold (be more selective)
        target = self.base_threshold + (network_risk - 0.5) * 0.4

        # Adjust for path availability
        target = target * (1 + (1 - path_factor) * 0.3)

        # Clamp to bounds
        target = max(self.min_threshold, min(self.max_threshold, target))

        # Smooth update
        self._current_threshold = (
            (1 - self.adaptation_rate) * self._current_threshold +
            self.adaptation_rate * target
        )

        # Record history
        self._history.append((time.time(), self._current_threshold))

    def should_accept_risk(self, risk_level: float) -> bool:
        """Check if a risk level is acceptable under current threshold."""
        return risk_level <= self._current_threshold

    def get_history(self) -> List[Tuple[float, float]]:
        """Get threshold adaptation history."""
        return self._history.copy()

    def reset(self) -> None:
        """Reset to base threshold."""
        self._current_threshold = self.base_threshold
        self._history.clear()
