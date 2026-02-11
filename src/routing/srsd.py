"""
SRSD - Sistema de Roteamento Seguro Distribuido.

This module provides:
- SRSDRouter: New compliant implementation using distributed routing
- LegacySRSDRouter: Original implementation for comparison (H1 baseline)
- AdaptiveSRSDRouter: Adaptive variant
- QKDIntegratedSRSDRouter: QKD-aware variant

The new SRSDRouter conforms to the SRSD specification:
- No global topology knowledge (Drawer-based local decisions)
- Structural discontinuity via Hiatus (CAR) nodes
- Repetition blocking (not penalization)
- QKD independent of routing decisions
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple
import random
import time
import math

from ..core.graph import NetworkGraph
from ..core.edge import Edge
from .baseline import Router, FlowRecord, RoutingStatistics
from .route_memory import RouteMemory
from .distributed import DistributedSRSDRouter, DistributedConfig


@dataclass
class SRSDConfig:
    """Configuration parameters for SRSD routing."""

    # Path selection (for legacy mode)
    k_paths: int = 5                    # Number of candidate paths to consider
    max_path_length_factor: float = 1.5  # Max path length as factor of shortest

    # Penalty weights (for legacy mode)
    recurrence_penalty: float = 2.0     # Penalty multiplier for repeated paths
    exposure_penalty: float = 1.5       # Penalty for exposed edges
    qkd_risk_penalty: float = 3.0       # Penalty for high QKD risk

    # Randomization (for legacy mode)
    selection_temperature: float = 1.0  # Temperature for probabilistic selection
    min_randomness: float = 0.1         # Minimum randomness in selection

    # Memory (for legacy mode)
    memory_decay_rate: float = 0.1      # How fast path memory decays
    memory_window: float = 3600.0       # Time window for frequency calculation

    # QKD integration (disabled by default - QKD should NOT influence routing)
    use_qkd_indicators: bool = False    # DEPRECATED: QKD should not influence routing
    qkd_threshold: float = 0.5          # DEPRECATED

    # Distributed mode configuration (NEW)
    use_distributed: bool = True        # Use new distributed implementation
    num_hiatus: int = 3                 # Number of Hiatus (CAR) nodes
    hiatus_placement: str = "random"    # Strategy: "random", "betweenness", "degree"
    blocking_window: int = 3            # Drawer blocking window

    # Seed
    seed: Optional[int] = None


class SRSDRouter(Router):
    """
    SRSD Router - Compliant implementation of secure distributed routing.

    This router uses the new distributed architecture:
    - Drawers for local routing decisions (no global topology knowledge)
    - Hiatus nodes for structural discontinuity
    - Onion packets to hide origin/destination
    - Repetition BLOCKING (not penalization)

    For backward compatibility, can also use legacy mode (use_distributed=False)
    which uses the original probabilistic path selection.
    """

    def __init__(self, graph: NetworkGraph,
                 config: Optional[SRSDConfig] = None,
                 qkd_risk_provider: Optional[Callable[[str, str], float]] = None):
        """
        Initialize SRSD router.

        Args:
            graph: Network graph
            config: SRSD configuration
            qkd_risk_provider: DEPRECATED - QKD should not influence routing
        """
        super().__init__(graph)
        self.config = config or SRSDConfig()

        # QKD risk provider is DEPRECATED but kept for backward compatibility
        if qkd_risk_provider is not None:
            import warnings
            warnings.warn(
                "qkd_risk_provider is deprecated. QKD should not influence routing decisions.",
                DeprecationWarning
            )
        self.qkd_risk_provider = qkd_risk_provider

        # Random state
        self._rng = random.Random(self.config.seed)

        if self.config.use_distributed:
            # NEW: Use distributed implementation
            dist_config = DistributedConfig(
                num_hiatus=self.config.num_hiatus,
                hiatus_placement=self.config.hiatus_placement,
                blocking_window=self.config.blocking_window,
                seed=self.config.seed
            )
            self._distributed = DistributedSRSDRouter(graph, dist_config)
        else:
            # LEGACY: Use original memory-based implementation
            self._distributed = None
            self.memory = RouteMemory(
                recency_weight=0.6,
                frequency_weight=0.4,
                decay_rate=self.config.memory_decay_rate,
                window_size=self.config.memory_window,
            )

    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._rng.seed(seed)
        if self._distributed:
            self._distributed.set_seed(seed)

    def route(self, source: str, destination: str,
              flow_id: Optional[str] = None) -> Optional[FlowRecord]:
        """
        Route using SRSD algorithm.

        In distributed mode (default):
        - Uses Drawer for local hop-by-hop decisions
        - Routes through Hiatus nodes for structural discontinuity
        - No global topology knowledge used

        In legacy mode:
        - Uses probabilistic path selection
        - Considers historical usage patterns
        - May use QKD risk indicators (deprecated)
        """
        if self._distributed:
            return self._distributed.route(source, destination, flow_id)
        else:
            return self._route_legacy(source, destination, flow_id)

    def _route_legacy(self, source: str, destination: str,
                      flow_id: Optional[str] = None) -> Optional[FlowRecord]:
        """Legacy routing implementation (for comparison)."""
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
        """Get candidate paths for routing (legacy mode)."""
        shortest = self.graph.shortest_path(source, destination)
        if shortest is None:
            return []

        shortest_len = len(shortest)
        max_len = int(shortest_len * self.config.max_path_length_factor)

        candidates = []
        try:
            for path in self.graph.all_simple_paths(source, destination, cutoff=max_len):
                candidates.append(path)
                if len(candidates) >= self.config.k_paths * 2:
                    break
        except Exception:
            candidates = self.graph.k_shortest_paths(
                source, destination, k=self.config.k_paths
            )

        valid_candidates = [
            p for p in candidates
            if len(p) <= max_len
        ][:self.config.k_paths]

        return valid_candidates if valid_candidates else ([shortest] if shortest else [])

    def _select_path(self, candidates: List[List[str]],
                     source: str, destination: str,
                     timestamp: float) -> Optional[List[str]]:
        """Select a path from candidates (legacy mode)."""
        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        scores = []
        for path in candidates:
            score = self._calculate_path_score(path, source, destination, timestamp)
            scores.append(score)

        probabilities = self._softmax_selection([-s for s in scores])

        min_prob = self.config.min_randomness / len(candidates)
        probabilities = [
            max(min_prob, p * (1 - self.config.min_randomness) + min_prob)
            for p in probabilities
        ]

        total = sum(probabilities)
        probabilities = [p / total for p in probabilities]

        r = self._rng.random()
        cumulative = 0.0
        for i, prob in enumerate(probabilities):
            cumulative += prob
            if r <= cumulative:
                return candidates[i]

        return candidates[-1]

    def _calculate_path_score(self, path: List[str],
                              source: str, destination: str,
                              timestamp: float) -> float:
        """Calculate score for a path (legacy mode)."""
        score = 0.0

        base_cost = self.graph.path_length(path, weight='weight')
        score += base_cost

        memory_penalty = self.memory.get_path_penalty(
            source, destination, path, timestamp
        )
        score += memory_penalty * self.config.recurrence_penalty

        edges = self.graph.path_edges(path)
        for edge in edges:
            score += edge.attributes.exposure * self.config.exposure_penalty
            score += edge.attributes.recurrence * self.config.recurrence_penalty * 0.5

            # QKD risk penalty (deprecated but kept for backward compatibility)
            if self.config.use_qkd_indicators:
                qkd_risk = self._get_qkd_risk(edge)
                if qkd_risk > self.config.qkd_threshold:
                    score += qkd_risk * self.config.qkd_risk_penalty

        return score

    def _get_qkd_risk(self, edge: Edge) -> float:
        """Get QKD risk indicator for an edge (deprecated)."""
        if self.qkd_risk_provider:
            return self.qkd_risk_provider(edge.source, edge.target)

        if edge.attributes.qkd_enabled:
            return min(1.0, edge.attributes.qkd_error_rate * 10)

        return 0.0

    def _softmax_selection(self, scores: List[float]) -> List[float]:
        """Convert scores to probabilities using softmax."""
        temp = self.config.selection_temperature

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
        if self._distributed:
            return {
                'drawer_stats': self._distributed.get_drawer_statistics(),
                'hiatus_stats': self._distributed.get_hiatus_statistics(),
                'path_reuse_rate': self.stats.path_reuse_rate,
                'unique_paths_used': self.stats.unique_paths,
            }
        else:
            return {
                'memory_stats': self.memory.get_overall_statistics(),
                'path_reuse_rate': self.stats.path_reuse_rate,
                'unique_paths_used': self.stats.unique_paths,
            }

    def get_statistics(self) -> RoutingStatistics:
        """Get routing statistics."""
        if self._distributed:
            return self._distributed.get_statistics()
        return self.stats

    def reset(self) -> None:
        """Reset router state."""
        super().reset()
        if self._distributed:
            self._distributed.reset()
        elif hasattr(self, 'memory'):
            self.memory.clear()


# Keep LegacySRSDRouter as alias for backward compatibility
class LegacySRSDRouter(SRSDRouter):
    """
    Legacy SRSD Router using the original probabilistic implementation.

    This router is kept for:
    - Backward compatibility
    - Comparison with the new distributed implementation (H1)
    - Testing the effectiveness of the new approach
    """

    def __init__(self, graph: NetworkGraph,
                 config: Optional[SRSDConfig] = None,
                 qkd_risk_provider: Optional[Callable[[str, str], float]] = None):
        if config is None:
            config = SRSDConfig(use_distributed=False)
        else:
            config.use_distributed = False

        super().__init__(graph, config, qkd_risk_provider)


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

        self._adaptation_history: List[Dict] = []
        self._current_threat_level: float = 0.5

    def update_threat_level(self, level: float) -> None:
        """Update perceived threat level (0-1)."""
        self._current_threat_level = max(0.0, min(1.0, level))
        self._adapt_parameters()

    def _adapt_parameters(self) -> None:
        """Adapt SRSD parameters based on current threat level."""
        base_config = SRSDConfig()
        threat = self._current_threat_level

        self.config.recurrence_penalty = base_config.recurrence_penalty * (1 + threat)
        self.config.k_paths = int(base_config.k_paths * (1 + threat * 0.5))
        self.config.selection_temperature = base_config.selection_temperature * (1 + threat * 0.5)
        self.config.min_randomness = min(0.3, base_config.min_randomness * (1 + threat))

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
    SRSD Router with QKD integration.

    NOTE: Per the SRSD specification, QKD should NOT influence routing decisions.
    This router is kept for backward compatibility but QKD risk is NOT used
    for path selection by default.

    QKD is used only for:
    - Key availability checking
    - Encryption/decryption operations
    - NOT for routing decisions
    """

    def __init__(self, graph: NetworkGraph,
                 config: Optional[SRSDConfig] = None,
                 qkd_channel_manager: Optional[object] = None):
        """
        Initialize QKD-integrated router.

        Args:
            graph: Network graph
            config: SRSD configuration
            qkd_channel_manager: QKD channel manager (for key operations only)
        """
        if config is None:
            config = SRSDConfig()

        # IMPORTANT: QKD does NOT influence routing in compliant mode
        # Set use_qkd_indicators to False regardless of input
        config.use_qkd_indicators = False

        super().__init__(graph, config)
        self.qkd_manager = qkd_channel_manager

    def has_qkd_keys(self, source: str, target: str) -> bool:
        """Check if QKD keys are available for a link."""
        if self.qkd_manager is None:
            return False

        try:
            return self.qkd_manager.has_keys(source, target)
        except Exception:
            return False

    def get_qkd_coverage(self) -> Dict:
        """Get statistics about QKD coverage in routing."""
        total_edges = len(self.graph.get_edges())
        qkd_edges = sum(1 for e in self.graph.get_edges() if e.attributes.qkd_enabled)

        return {
            'total_edges': total_edges,
            'qkd_enabled_edges': qkd_edges,
            'qkd_coverage_ratio': qkd_edges / total_edges if total_edges > 0 else 0.0,
        }
