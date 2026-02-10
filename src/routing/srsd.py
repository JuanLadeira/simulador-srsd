"""
SRSD - Sistema de Roteamento Seguro Distribuído.

Implements non-deterministic routing that avoids systematic path reuse
while considering QKD risk indicators when available.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
import random
import time
import math

from ..core.graph import NetworkGraph
from ..core.edge import Edge
from .baseline import Router, FlowRecord, RoutingStatistics
from .route_memory import RouteMemory


@dataclass
class SRSDConfig:
    """Configuration parameters for SRSD routing."""

    # Path selection
    k_paths: int = 5                    # Number of candidate paths to consider
    max_path_length_factor: float = 1.5  # Max path length as factor of shortest

    # Penalty weights
    recurrence_penalty: float = 2.0     # Penalty multiplier for repeated paths
    exposure_penalty: float = 1.5       # Penalty for exposed edges
    qkd_risk_penalty: float = 3.0       # Penalty for high QKD risk

    # Randomization
    selection_temperature: float = 1.0  # Temperature for probabilistic selection
    min_randomness: float = 0.1         # Minimum randomness in selection

    # Memory
    memory_decay_rate: float = 0.1      # How fast path memory decays
    memory_window: float = 3600.0       # Time window for frequency calculation

    # QKD integration
    use_qkd_indicators: bool = False    # Whether to use QKD risk indicators
    qkd_threshold: float = 0.5          # Risk threshold for QKD-based avoidance


class SRSDRouter(Router):
    """
    SRSD Router - Implements non-deterministic secure routing.

    Key features:
    - Avoids systematic path reuse (reduces structural predictability)
    - Considers multiple candidate paths
    - Integrates QKD risk indicators when available
    - Maintains route memory for diversity enforcement
    """

    def __init__(self, graph: NetworkGraph,
                 config: Optional[SRSDConfig] = None,
                 qkd_risk_provider: Optional[Callable[[str, str], float]] = None):
        """
        Initialize SRSD router.

        Args:
            graph: Network graph
            config: SRSD configuration
            qkd_risk_provider: Function that returns QKD risk for an edge
        """
        super().__init__(graph)
        self.config = config or SRSDConfig()
        self.qkd_risk_provider = qkd_risk_provider

        # Initialize route memory
        self.memory = RouteMemory(
            recency_weight=0.6,
            frequency_weight=0.4,
            decay_rate=self.config.memory_decay_rate,
            window_size=self.config.memory_window,
        )

        # Random state for reproducibility
        self._rng = random.Random()

    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._rng.seed(seed)

    def route(self, source: str, destination: str,
              flow_id: Optional[str] = None) -> Optional[FlowRecord]:
        """
        Route using SRSD algorithm.

        Selects path based on:
        1. Path availability and validity
        2. Historical usage patterns (avoid repetition)
        3. Structural exposure of edges
        4. QKD risk indicators (if enabled)
        """
        timestamp = time.time()
        fid = flow_id or f"flow_{source}_{destination}_{timestamp}"

        # Get candidate paths
        candidates = self._get_candidate_paths(source, destination)
        if not candidates:
            self.stats.record_failure()
            return None

        # Score and select path
        selected_path = self._select_path(candidates, source, destination, timestamp)

        if selected_path is None:
            self.stats.record_failure()
            return None

        # Calculate metrics
        latency = self._calculate_latency(selected_path)

        # Record in memory
        self.memory.record_path(source, destination, selected_path, fid, timestamp)

        # Record edge usage
        self._record_path_usage(selected_path, timestamp)

        # Create flow record
        flow = FlowRecord(
            flow_id=fid,
            source=source,
            destination=destination,
            path=selected_path,
            timestamp=timestamp,
            latency=latency,
        )

        self.stats.record_success(flow)
        return flow

    def _get_candidate_paths(self, source: str, destination: str) -> List[List[str]]:
        """
        Get candidate paths for routing.

        Returns up to k_paths paths that meet length constraints.
        """
        # Get shortest path length for reference
        shortest = self.graph.shortest_path(source, destination)
        if shortest is None:
            return []

        shortest_len = len(shortest)
        max_len = int(shortest_len * self.config.max_path_length_factor)

        # Get k shortest paths
        candidates = []
        try:
            for path in self.graph.all_simple_paths(source, destination, cutoff=max_len):
                candidates.append(path)
                if len(candidates) >= self.config.k_paths * 2:  # Get extras for filtering
                    break
        except Exception:
            # Fall back to k_shortest_paths
            candidates = self.graph.k_shortest_paths(
                source, destination, k=self.config.k_paths
            )

        # Filter by length and limit
        valid_candidates = [
            p for p in candidates
            if len(p) <= max_len
        ][:self.config.k_paths]

        return valid_candidates if valid_candidates else ([shortest] if shortest else [])

    def _select_path(self, candidates: List[List[str]],
                     source: str, destination: str,
                     timestamp: float) -> Optional[List[str]]:
        """
        Select a path from candidates using SRSD scoring.

        Uses weighted scoring with soft randomization.
        """
        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        # Score each candidate
        scores = []
        for path in candidates:
            score = self._calculate_path_score(path, source, destination, timestamp)
            scores.append(score)

        # Convert scores to selection probabilities using softmax
        # Lower score = better, so we negate
        probabilities = self._softmax_selection([-s for s in scores])

        # Add minimum randomness
        min_prob = self.config.min_randomness / len(candidates)
        probabilities = [
            max(min_prob, p * (1 - self.config.min_randomness) + min_prob)
            for p in probabilities
        ]

        # Normalize
        total = sum(probabilities)
        probabilities = [p / total for p in probabilities]

        # Select based on probabilities
        r = self._rng.random()
        cumulative = 0.0
        for i, prob in enumerate(probabilities):
            cumulative += prob
            if r <= cumulative:
                return candidates[i]

        # Fallback to last candidate
        return candidates[-1]

    def _calculate_path_score(self, path: List[str],
                              source: str, destination: str,
                              timestamp: float) -> float:
        """
        Calculate score for a path (lower is better).

        Considers:
        - Base path length/cost
        - Memory penalty (recurrence)
        - Edge exposure
        - QKD risk (if enabled)
        """
        score = 0.0

        # Base cost (path length)
        base_cost = self.graph.path_length(path, weight='weight')
        score += base_cost

        # Memory penalty (recurrence avoidance)
        memory_penalty = self.memory.get_path_penalty(
            source, destination, path, timestamp
        )
        score += memory_penalty * self.config.recurrence_penalty

        # Edge-level penalties
        edges = self.graph.path_edges(path)
        for edge in edges:
            # Exposure penalty
            score += edge.attributes.exposure * self.config.exposure_penalty

            # Recurrence from edge attributes
            score += edge.attributes.recurrence * self.config.recurrence_penalty * 0.5

            # QKD risk penalty (if enabled)
            if self.config.use_qkd_indicators:
                qkd_risk = self._get_qkd_risk(edge)
                if qkd_risk > self.config.qkd_threshold:
                    score += qkd_risk * self.config.qkd_risk_penalty

        return score

    def _get_qkd_risk(self, edge: Edge) -> float:
        """
        Get QKD risk indicator for an edge.

        Uses external provider if available, otherwise uses edge attributes.
        """
        if self.qkd_risk_provider:
            return self.qkd_risk_provider(edge.source, edge.target)

        # Default: use QBER as risk indicator
        if edge.attributes.qkd_enabled:
            # Higher QBER = higher risk
            return min(1.0, edge.attributes.qkd_error_rate * 10)

        return 0.0

    def _softmax_selection(self, scores: List[float]) -> List[float]:
        """Convert scores to probabilities using softmax."""
        temp = self.config.selection_temperature

        # Numerical stability: subtract max
        max_score = max(scores)
        exp_scores = [math.exp((s - max_score) / temp) for s in scores]
        total = sum(exp_scores)

        if total == 0:
            return [1.0 / len(scores)] * len(scores)

        return [e / total for e in exp_scores]

    def _calculate_latency(self, path: List[str]) -> float:
        """Calculate total latency for a path."""
        total = 0.0
        for i in range(len(path) - 1):
            edge = self.graph.get_edge_between(path[i], path[i + 1])
            if edge:
                total += edge.attributes.latency
        return total

    def _record_path_usage(self, path: List[str], timestamp: float) -> None:
        """Record usage of edges in the path."""
        for i in range(len(path) - 1):
            edge = self.graph.get_edge_between(path[i], path[i + 1])
            if edge:
                edge.record_usage(timestamp)

            node = self.graph.get_node(path[i])
            if node:
                node.stats.record_forward()

    def get_diversity_metrics(self) -> Dict:
        """Get metrics about routing diversity."""
        return {
            'memory_stats': self.memory.get_overall_statistics(),
            'path_reuse_rate': self.stats.path_reuse_rate,
            'unique_paths_used': self.stats.unique_paths,
        }

    def reset(self) -> None:
        """Reset router state."""
        super().reset()
        self.memory.clear()


class AdaptiveSRSDRouter(SRSDRouter):
    """
    Adaptive SRSD Router that adjusts parameters based on observed conditions.

    Can increase diversity when adversarial patterns are detected
    or reduce overhead when risk is low.
    """

    def __init__(self, graph: NetworkGraph,
                 config: Optional[SRSDConfig] = None,
                 qkd_risk_provider: Optional[Callable[[str, str], float]] = None):
        super().__init__(graph, config, qkd_risk_provider)

        # Adaptation state
        self._adaptation_history: List[Dict] = []
        self._current_threat_level: float = 0.5  # 0-1

    def update_threat_level(self, level: float) -> None:
        """
        Update perceived threat level.

        Higher threat = more diversity, less predictability.
        """
        self._current_threat_level = max(0.0, min(1.0, level))

        # Adapt parameters based on threat level
        self._adapt_parameters()

    def _adapt_parameters(self) -> None:
        """Adapt SRSD parameters based on current threat level."""
        base_config = SRSDConfig()

        # Higher threat = more aggressive diversity
        threat = self._current_threat_level

        self.config.recurrence_penalty = base_config.recurrence_penalty * (1 + threat)
        self.config.k_paths = int(base_config.k_paths * (1 + threat * 0.5))
        self.config.selection_temperature = base_config.selection_temperature * (1 + threat * 0.5)
        self.config.min_randomness = min(0.3, base_config.min_randomness * (1 + threat))

        # Record adaptation
        self._adaptation_history.append({
            'timestamp': time.time(),
            'threat_level': threat,
            'recurrence_penalty': self.config.recurrence_penalty,
            'k_paths': self.config.k_paths,
        })

    def get_adaptation_history(self) -> List[Dict]:
        """Get history of parameter adaptations."""
        return self._adaptation_history.copy()


class QKDIntegratedSRSDRouter(SRSDRouter):
    """
    SRSD Router with full QKD integration.

    Uses QKD channel state to make routing decisions
    and can adapt to quantum channel conditions.
    """

    def __init__(self, graph: NetworkGraph,
                 config: Optional[SRSDConfig] = None,
                 qkd_channel_manager: Optional[object] = None):
        """
        Initialize QKD-integrated router.

        Args:
            graph: Network graph
            config: SRSD configuration
            qkd_channel_manager: QKD channel manager for risk indicators
        """
        # Enable QKD by default
        if config is None:
            config = SRSDConfig(use_qkd_indicators=True)
        else:
            config.use_qkd_indicators = True

        super().__init__(graph, config)
        self.qkd_manager = qkd_channel_manager

        # Override risk provider if manager available
        if qkd_channel_manager:
            self.qkd_risk_provider = self._get_qkd_risk_from_manager

    def _get_qkd_risk_from_manager(self, source: str, target: str) -> float:
        """Get QKD risk from channel manager."""
        if self.qkd_manager is None:
            return 0.0

        try:
            return self.qkd_manager.get_channel_risk(source, target)
        except Exception:
            return 0.0

    def route_with_qkd_priority(self, source: str, destination: str,
                                 flow_id: Optional[str] = None,
                                 require_qkd: bool = False) -> Optional[FlowRecord]:
        """
        Route with QKD path priority.

        Can require that the selected path has QKD capability.
        """
        if not require_qkd:
            return self.route(source, destination, flow_id)

        # Get candidates that have QKD capability
        candidates = self._get_candidate_paths(source, destination)
        qkd_candidates = []

        for path in candidates:
            if self._path_has_qkd(path):
                qkd_candidates.append(path)

        if not qkd_candidates:
            self.stats.record_failure()
            return None

        # Route using only QKD-capable paths
        timestamp = time.time()
        fid = flow_id or f"flow_{source}_{destination}_{timestamp}"

        selected = self._select_path(qkd_candidates, source, destination, timestamp)
        if selected is None:
            self.stats.record_failure()
            return None

        latency = self._calculate_latency(selected)
        self.memory.record_path(source, destination, selected, fid, timestamp)
        self._record_path_usage(selected, timestamp)

        flow = FlowRecord(
            flow_id=fid,
            source=source,
            destination=destination,
            path=selected,
            timestamp=timestamp,
            latency=latency,
        )

        self.stats.record_success(flow)
        return flow

    def _path_has_qkd(self, path: List[str]) -> bool:
        """Check if all edges in path have QKD capability."""
        for i in range(len(path) - 1):
            edge = self.graph.get_edge_between(path[i], path[i + 1])
            if edge is None or not edge.attributes.qkd_enabled:
                return False
        return True

    def get_qkd_coverage(self) -> Dict:
        """Get statistics about QKD coverage in routing."""
        total_edges = len(self.graph.get_edges())
        qkd_edges = sum(1 for e in self.graph.get_edges() if e.attributes.qkd_enabled)

        return {
            'total_edges': total_edges,
            'qkd_enabled_edges': qkd_edges,
            'qkd_coverage_ratio': qkd_edges / total_edges if total_edges > 0 else 0.0,
        }
