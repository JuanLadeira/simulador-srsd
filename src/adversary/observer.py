"""
Adversary Observer - Passive structural adversary model.

Implements an adversary that:
- Cannot access packet contents (encryption assumed)
- Cannot break cryptography
- CAN observe network structure and traffic patterns
- CAN correlate entry/exit timing
- CAN fingerprint flow patterns
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import time

from ..core.graph import NetworkGraph
from ..routing.baseline import FlowRecord


@dataclass
class Observation:
    """Single observation made by the adversary."""

    timestamp: float
    node_id: str
    observation_type: str  # 'entry', 'exit', 'transit'
    flow_signature: Optional[str] = None  # Timing-based signature
    packet_size: Optional[int] = None


@dataclass
class FlowCorrelation:
    """Correlation between entry and exit observations."""

    entry_node: str
    exit_node: str
    confidence: float  # 0-1
    timing_delta: float
    observations: int = 0


class StructuralObserver:
    """
    Passive adversary that observes network structure and traffic patterns.

    This observer models an adversary who:
    - Has access to network topology information
    - Can observe traffic at certain vantage points
    - Uses timing analysis to correlate flows
    - Builds fingerprints of routing patterns
    """

    def __init__(self, graph: NetworkGraph,
                 vantage_points: Optional[List[str]] = None,
                 timing_window: float = 0.1):
        """
        Initialize structural observer.

        Args:
            graph: Network graph being observed
            vantage_points: Nodes where adversary can observe traffic
                           (None = all nodes)
            timing_window: Time window for correlating observations (seconds)
        """
        self.graph = graph
        self.timing_window = timing_window

        # Set vantage points (default: all nodes)
        if vantage_points is None:
            self.vantage_points = set(n.id for n in graph.get_nodes())
        else:
            self.vantage_points = set(vantage_points)

        # Observation storage
        self._observations: List[Observation] = []
        self._flow_observations: Dict[str, List[Observation]] = defaultdict(list)

        # Pattern analysis
        self._entry_exit_correlations: Dict[Tuple[str, str], FlowCorrelation] = {}
        self._timing_patterns: Dict[str, List[float]] = defaultdict(list)
        self._path_fingerprints: Dict[str, int] = defaultdict(int)

        # Flow tracking
        self._active_flows: Dict[str, Dict] = {}
        self._completed_flows: List[Dict] = []

    def observe_flow(self, flow: FlowRecord) -> None:
        """
        Observe a flow passing through the network.

        The adversary sees entry/exit points and timing,
        but not the actual path taken.
        """
        timestamp = flow.timestamp

        # Check if source is visible
        if flow.source in self.vantage_points:
            obs = Observation(
                timestamp=timestamp,
                node_id=flow.source,
                observation_type='entry',
            )
            self._observations.append(obs)
            self._flow_observations[flow.flow_id].append(obs)

        # Check if destination is visible
        if flow.destination in self.vantage_points:
            exit_time = timestamp + flow.latency / 1000.0  # Convert ms to seconds
            obs = Observation(
                timestamp=exit_time,
                node_id=flow.destination,
                observation_type='exit',
            )
            self._observations.append(obs)
            self._flow_observations[flow.flow_id].append(obs)

        # Update correlation analysis
        self._update_correlations(flow)

        # Update path fingerprinting
        self._update_fingerprint(flow)

    def observe_path_nodes(self, flow: FlowRecord) -> None:
        """
        Observe which nodes a flow traverses (if visible).

        More detailed observation for intermediate nodes.
        """
        timestamp = flow.timestamp
        cumulative_latency = 0.0

        for i, node_id in enumerate(flow.path):
            if node_id in self.vantage_points:
                obs_type = 'entry' if i == 0 else ('exit' if i == len(flow.path) - 1 else 'transit')
                obs = Observation(
                    timestamp=timestamp + cumulative_latency / 1000.0,
                    node_id=node_id,
                    observation_type=obs_type,
                )
                self._observations.append(obs)
                self._flow_observations[flow.flow_id].append(obs)

            # Update cumulative latency
            if i < len(flow.path) - 1:
                edge = self.graph.get_edge_between(flow.path[i], flow.path[i + 1])
                if edge:
                    cumulative_latency += edge.attributes.latency

    def _update_correlations(self, flow: FlowRecord) -> None:
        """Update entry-exit correlation statistics."""
        key = (flow.source, flow.destination)

        if key not in self._entry_exit_correlations:
            self._entry_exit_correlations[key] = FlowCorrelation(
                entry_node=flow.source,
                exit_node=flow.destination,
                confidence=0.0,
                timing_delta=flow.latency,
            )

        corr = self._entry_exit_correlations[key]
        corr.observations += 1

        # Update timing delta (running average)
        alpha = 0.1  # Exponential moving average factor
        corr.timing_delta = (1 - alpha) * corr.timing_delta + alpha * flow.latency

    def _update_fingerprint(self, flow: FlowRecord) -> None:
        """Update path fingerprinting based on observable characteristics."""
        # Create fingerprint from timing and hop count
        # (adversary can estimate hops from latency)
        estimated_hops = int(flow.latency / 10)  # Rough estimate
        fingerprint = f"{flow.source}->{flow.destination}:{estimated_hops}"

        self._path_fingerprints[fingerprint] += 1

    def correlate_entry_exit(self) -> Dict[Tuple[str, str], float]:
        """
        Attempt to correlate entry and exit points.

        Returns correlation confidence for each observed pair.
        """
        correlations = {}

        for key, corr in self._entry_exit_correlations.items():
            # Confidence based on observation count and timing consistency
            if corr.observations > 0:
                # More observations = higher confidence
                count_factor = min(1.0, corr.observations / 100.0)

                # Consistent timing = higher confidence
                # (would need timing variance, simplified here)
                timing_factor = 0.8

                corr.confidence = count_factor * timing_factor
                correlations[key] = corr.confidence

        return correlations

    def identify_recurring_flows(self, min_occurrences: int = 3) -> List[Dict]:
        """
        Identify flows that appear to recur (same pattern).

        Returns list of recurring flow patterns.
        """
        recurring = []

        for fingerprint, count in self._path_fingerprints.items():
            if count >= min_occurrences:
                parts = fingerprint.split(':')
                endpoints = parts[0].split('->')

                recurring.append({
                    'source': endpoints[0],
                    'destination': endpoints[1],
                    'estimated_hops': int(parts[1]) if len(parts) > 1 else 0,
                    'occurrences': count,
                })

        return sorted(recurring, key=lambda x: x['occurrences'], reverse=True)

    def get_observation_statistics(self) -> Dict:
        """Get statistics about observations."""
        total_obs = len(self._observations)
        entry_obs = sum(1 for o in self._observations if o.observation_type == 'entry')
        exit_obs = sum(1 for o in self._observations if o.observation_type == 'exit')
        transit_obs = sum(1 for o in self._observations if o.observation_type == 'transit')

        return {
            'total_observations': total_obs,
            'entry_observations': entry_obs,
            'exit_observations': exit_obs,
            'transit_observations': transit_obs,
            'unique_flows_observed': len(self._flow_observations),
            'vantage_point_coverage': len(self.vantage_points) / self.graph.num_nodes,
        }

    def get_correlation_statistics(self) -> Dict:
        """Get entry-exit correlation statistics."""
        correlations = self.correlate_entry_exit()

        if not correlations:
            return {
                'num_correlations': 0,
                'avg_confidence': 0.0,
                'high_confidence_pairs': 0,
            }

        avg_conf = sum(correlations.values()) / len(correlations)
        high_conf = sum(1 for c in correlations.values() if c > 0.7)

        return {
            'num_correlations': len(correlations),
            'avg_confidence': avg_conf,
            'high_confidence_pairs': high_conf,
            'max_confidence': max(correlations.values()),
        }

    def reset(self) -> None:
        """Reset all observations."""
        self._observations.clear()
        self._flow_observations.clear()
        self._entry_exit_correlations.clear()
        self._timing_patterns.clear()
        self._path_fingerprints.clear()
        self._active_flows.clear()
        self._completed_flows.clear()


class TimingAnalyzer:
    """
    Analyzes timing patterns to infer routing behavior.

    Uses statistical analysis of packet timing to identify patterns.
    """

    def __init__(self, window_size: float = 1.0):
        """
        Initialize timing analyzer.

        Args:
            window_size: Time window for grouping observations
        """
        self.window_size = window_size
        self._timing_data: Dict[str, List[float]] = defaultdict(list)
        self._inter_arrival_times: Dict[str, List[float]] = defaultdict(list)

    def record_timing(self, node_id: str, timestamp: float) -> None:
        """Record a timing observation at a node."""
        self._timing_data[node_id].append(timestamp)

        # Calculate inter-arrival time
        timings = self._timing_data[node_id]
        if len(timings) > 1:
            iat = timings[-1] - timings[-2]
            self._inter_arrival_times[node_id].append(iat)

    def get_timing_pattern(self, node_id: str) -> Optional[Dict]:
        """
        Analyze timing pattern at a node.

        Returns pattern characteristics.
        """
        if node_id not in self._inter_arrival_times:
            return None

        iats = self._inter_arrival_times[node_id]
        if len(iats) < 2:
            return None

        import statistics

        return {
            'mean_iat': statistics.mean(iats),
            'stdev_iat': statistics.stdev(iats) if len(iats) > 1 else 0,
            'min_iat': min(iats),
            'max_iat': max(iats),
            'sample_count': len(iats),
        }

    def detect_periodicity(self, node_id: str, tolerance: float = 0.1) -> Optional[float]:
        """
        Detect if traffic at a node shows periodicity.

        Returns detected period if found, None otherwise.
        """
        if node_id not in self._inter_arrival_times:
            return None

        iats = self._inter_arrival_times[node_id]
        if len(iats) < 10:
            return None

        import statistics

        mean_iat = statistics.mean(iats)
        stdev_iat = statistics.stdev(iats)

        # Check if variation is within tolerance (indicates periodicity)
        if stdev_iat / mean_iat < tolerance:
            return mean_iat

        return None

    def reset(self) -> None:
        """Reset timing data."""
        self._timing_data.clear()
        self._inter_arrival_times.clear()


class PathInferenceEngine:
    """
    Attempts to infer routing paths from structural observations.

    Uses network topology knowledge and timing analysis.
    """

    def __init__(self, graph: NetworkGraph, observer: StructuralObserver):
        """
        Initialize path inference engine.

        Args:
            graph: Network graph
            observer: Structural observer for input data
        """
        self.graph = graph
        self.observer = observer

    def infer_likely_paths(self, source: str, destination: str,
                           num_paths: int = 3) -> List[Tuple[List[str], float]]:
        """
        Infer most likely paths between source and destination.

        Returns list of (path, probability) tuples.
        """
        # Get all possible paths
        all_paths = list(self.graph.all_simple_paths(source, destination, cutoff=10))

        if not all_paths:
            return []

        # Score paths based on structural analysis
        scored_paths = []
        for path in all_paths:
            score = self._score_path_likelihood(path)
            scored_paths.append((path, score))

        # Sort by score (higher is more likely)
        scored_paths.sort(key=lambda x: x[1], reverse=True)

        # Normalize to probabilities
        total_score = sum(s for _, s in scored_paths)
        if total_score > 0:
            scored_paths = [(p, s / total_score) for p, s in scored_paths]

        return scored_paths[:num_paths]

    def _score_path_likelihood(self, path: List[str]) -> float:
        """
        Score how likely a path is based on adversary knowledge.

        Higher score = more likely to be used.
        """
        score = 1.0

        # Shorter paths are generally more likely (baseline assumption)
        length_factor = 1.0 / len(path)
        score *= length_factor

        # Paths through high-traffic nodes are more likely
        for node_id in path:
            node = self.graph.get_node(node_id)
            if node:
                # Use node degree as proxy for importance
                degree = len(node.outgoing_edges) + len(node.incoming_edges)
                score *= (1 + degree * 0.1)

        # Check if we've observed this path pattern before
        fingerprint = '->'.join(path)
        if fingerprint in self.observer._path_fingerprints:
            score *= (1 + self.observer._path_fingerprints[fingerprint] * 0.5)

        return score

    def calculate_inference_success_rate(self, actual_flows: List[FlowRecord]) -> float:
        """
        Calculate how often the adversary correctly infers paths.

        Args:
            actual_flows: List of actual flows with known paths

        Returns:
            Success rate (0-1)
        """
        if not actual_flows:
            return 0.0

        correct = 0
        for flow in actual_flows:
            inferred = self.infer_likely_paths(flow.source, flow.destination, num_paths=1)
            if inferred and inferred[0][0] == flow.path:
                correct += 1

        return correct / len(actual_flows)
