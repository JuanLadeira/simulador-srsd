"""
Adversary Metrics - Quantify adversarial inference capabilities.

Provides metrics to measure:
- Entry-exit correlation success
- Flow fingerprinting accuracy
- Path entropy (predictability)
- Recurrent flow identification rate
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import math

from ..core.graph import NetworkGraph
from ..routing.baseline import FlowRecord, RoutingStatistics


@dataclass
class CorrelationMetrics:
    """Metrics for entry-exit correlation attacks."""

    total_flows: int = 0
    correctly_correlated: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        """Precision of correlation (correctly correlated / predicted)."""
        predicted = self.correctly_correlated + self.false_positives
        if predicted == 0:
            return 0.0
        return self.correctly_correlated / predicted

    @property
    def recall(self) -> float:
        """Recall of correlation (correctly correlated / actual)."""
        actual = self.correctly_correlated + self.false_negatives
        if actual == 0:
            return 0.0
        return self.correctly_correlated / actual

    @property
    def f1_score(self) -> float:
        """F1 score combining precision and recall."""
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)

    @property
    def accuracy(self) -> float:
        """Overall accuracy."""
        if self.total_flows == 0:
            return 0.0
        return self.correctly_correlated / self.total_flows


@dataclass
class FingerprintingMetrics:
    """Metrics for flow fingerprinting attacks."""

    total_fingerprints: int = 0
    unique_fingerprints: int = 0
    correctly_identified: int = 0
    misidentified: int = 0

    @property
    def identification_rate(self) -> float:
        """Rate of correct flow identification."""
        total = self.correctly_identified + self.misidentified
        if total == 0:
            return 0.0
        return self.correctly_identified / total

    @property
    def fingerprint_diversity(self) -> float:
        """Diversity of fingerprints (higher = harder to identify)."""
        if self.total_fingerprints == 0:
            return 0.0
        return self.unique_fingerprints / self.total_fingerprints


def calculate_path_entropy(routing_stats: RoutingStatistics) -> float:
    """
    Calculate Shannon entropy of path distribution.

    Higher entropy = more unpredictable routing.
    Lower entropy = more predictable (vulnerable to adversary).

    Args:
        routing_stats: Routing statistics with path usage data

    Returns:
        Entropy in bits
    """
    path_usage = routing_stats.path_usage

    if not path_usage:
        return 0.0

    total_uses = sum(path_usage.values())
    if total_uses == 0:
        return 0.0

    entropy = 0.0
    for count in path_usage.values():
        if count > 0:
            prob = count / total_uses
            entropy -= prob * math.log2(prob)

    return entropy


def calculate_normalized_entropy(routing_stats: RoutingStatistics) -> float:
    """
    Calculate normalized path entropy (0-1).

    1.0 = maximum entropy (uniform distribution)
    0.0 = minimum entropy (single path used)

    Args:
        routing_stats: Routing statistics

    Returns:
        Normalized entropy (0-1)
    """
    entropy = calculate_path_entropy(routing_stats)

    # Maximum possible entropy is log2(num_unique_paths)
    num_paths = len(routing_stats.path_usage)
    if num_paths <= 1:
        return 0.0

    max_entropy = math.log2(num_paths)
    return entropy / max_entropy if max_entropy > 0 else 0.0


def calculate_recurrence_rate(routing_stats: RoutingStatistics) -> float:
    """
    Calculate how often paths are reused.

    Higher rate = more predictable routing.

    Returns:
        Recurrence rate (0-1 where 1 means always same path)
    """
    if routing_stats.successful_routes <= 1:
        return 0.0

    path_usage = routing_stats.path_usage
    if not path_usage:
        return 0.0

    total_uses = sum(path_usage.values())
    most_used = max(path_usage.values())

    # Recurrence = how concentrated usage is on single path
    return most_used / total_uses


def calculate_flow_identification_rate(
    observed_flows: List[FlowRecord],
    actual_flows: List[FlowRecord],
    timing_tolerance: float = 0.1
) -> float:
    """
    Calculate rate at which flows can be correctly identified.

    Uses timing correlation to match flows.

    Args:
        observed_flows: Flows as seen by adversary (may have less info)
        actual_flows: Actual flows with full information
        timing_tolerance: Tolerance for timing matching (seconds)

    Returns:
        Identification rate (0-1)
    """
    if not actual_flows:
        return 0.0

    correctly_identified = 0

    for actual in actual_flows:
        for observed in observed_flows:
            # Check if timing matches within tolerance
            if abs(actual.timestamp - observed.timestamp) <= timing_tolerance:
                # Check if endpoints match
                if (actual.source == observed.source and
                    actual.destination == observed.destination):
                    correctly_identified += 1
                    break

    return correctly_identified / len(actual_flows)


class AdversaryCapabilityMetrics:
    """
    Comprehensive metrics for adversary capabilities.

    Measures various attack vectors and their success rates.
    """

    def __init__(self, graph: NetworkGraph):
        """
        Initialize metrics calculator.

        Args:
            graph: Network graph
        """
        self.graph = graph

        # Collected data
        self._baseline_flows: List[FlowRecord] = []
        self._srsd_flows: List[FlowRecord] = []

    def add_baseline_flow(self, flow: FlowRecord) -> None:
        """Add a flow from baseline routing."""
        self._baseline_flows.append(flow)

    def add_srsd_flow(self, flow: FlowRecord) -> None:
        """Add a flow from SRSD routing."""
        self._srsd_flows.append(flow)

    def calculate_correlation_metrics(self,
                                       flows: List[FlowRecord]) -> CorrelationMetrics:
        """
        Calculate correlation attack metrics.

        Simulates adversary attempting to correlate entry-exit pairs.
        """
        metrics = CorrelationMetrics(total_flows=len(flows))

        # Group flows by source-destination pair
        flow_pairs: Dict[Tuple[str, str], List[FlowRecord]] = defaultdict(list)
        for flow in flows:
            key = (flow.source, flow.destination)
            flow_pairs[key].append(flow)

        # Simulate correlation attack
        for (src, dst), pair_flows in flow_pairs.items():
            if len(pair_flows) >= 2:
                # Adversary can likely correlate repeated patterns
                metrics.correctly_correlated += len(pair_flows) - 1

        return metrics

    def calculate_fingerprinting_metrics(self,
                                          flows: List[FlowRecord]) -> FingerprintingMetrics:
        """
        Calculate fingerprinting attack metrics.

        Measures how well flows can be fingerprinted by their patterns.
        """
        metrics = FingerprintingMetrics()

        # Create fingerprints based on path characteristics
        fingerprints: Dict[str, List[FlowRecord]] = defaultdict(list)

        for flow in flows:
            # Create fingerprint from observable characteristics
            fp = self._create_fingerprint(flow)
            fingerprints[fp].append(flow)
            metrics.total_fingerprints += 1

        metrics.unique_fingerprints = len(fingerprints)

        # Check identification (non-unique fingerprints can be identified)
        for fp, fp_flows in fingerprints.items():
            if len(fp_flows) > 1:
                # Multiple flows with same fingerprint = identifiable pattern
                metrics.correctly_identified += len(fp_flows)
            else:
                metrics.misidentified += 1

        return metrics

    def _create_fingerprint(self, flow: FlowRecord) -> str:
        """Create a fingerprint from observable flow characteristics."""
        # Use hop count and latency range as fingerprint
        hop_bin = flow.hops
        latency_bin = int(flow.latency / 10)  # 10ms bins
        return f"{flow.source}-{flow.destination}-h{hop_bin}-l{latency_bin}"

    def calculate_path_predictability(self, flows: List[FlowRecord]) -> Dict:
        """
        Calculate how predictable the routing is.

        Returns various predictability metrics.
        """
        if not flows:
            return {
                'entropy': 0.0,
                'normalized_entropy': 0.0,
                'recurrence_rate': 0.0,
                'unique_path_ratio': 0.0,
            }

        # Group flows by source-destination
        sd_flows: Dict[Tuple[str, str], List[List[str]]] = defaultdict(list)
        for flow in flows:
            key = (flow.source, flow.destination)
            sd_flows[key].append(flow.path)

        # Calculate metrics per pair
        entropies = []
        recurrence_rates = []
        unique_ratios = []

        for (src, dst), paths in sd_flows.items():
            if len(paths) > 1:
                # Count path occurrences
                path_counts: Dict[str, int] = defaultdict(int)
                for path in paths:
                    path_key = '->'.join(path)
                    path_counts[path_key] += 1

                # Calculate entropy
                total = len(paths)
                entropy = 0.0
                for count in path_counts.values():
                    prob = count / total
                    entropy -= prob * math.log2(prob)
                entropies.append(entropy)

                # Calculate recurrence
                most_used = max(path_counts.values())
                recurrence_rates.append(most_used / total)

                # Unique ratio
                unique_ratios.append(len(path_counts) / total)

        return {
            'entropy': sum(entropies) / len(entropies) if entropies else 0.0,
            'normalized_entropy': calculate_normalized_entropy(
                self._flows_to_stats(flows)
            ),
            'recurrence_rate': sum(recurrence_rates) / len(recurrence_rates) if recurrence_rates else 0.0,
            'unique_path_ratio': sum(unique_ratios) / len(unique_ratios) if unique_ratios else 0.0,
        }

    def _flows_to_stats(self, flows: List[FlowRecord]) -> RoutingStatistics:
        """Convert flow list to RoutingStatistics for metric calculation."""
        stats = RoutingStatistics()
        for flow in flows:
            stats.record_success(flow)
        return stats

    def compare_baseline_vs_srsd(self) -> Dict:
        """
        Compare adversary capabilities against baseline vs SRSD.

        Returns comparative metrics showing SRSD effectiveness.
        """
        baseline_corr = self.calculate_correlation_metrics(self._baseline_flows)
        srsd_corr = self.calculate_correlation_metrics(self._srsd_flows)

        baseline_fp = self.calculate_fingerprinting_metrics(self._baseline_flows)
        srsd_fp = self.calculate_fingerprinting_metrics(self._srsd_flows)

        baseline_pred = self.calculate_path_predictability(self._baseline_flows)
        srsd_pred = self.calculate_path_predictability(self._srsd_flows)

        return {
            'correlation': {
                'baseline_accuracy': baseline_corr.accuracy,
                'srsd_accuracy': srsd_corr.accuracy,
                'improvement': baseline_corr.accuracy - srsd_corr.accuracy,
            },
            'fingerprinting': {
                'baseline_identification_rate': baseline_fp.identification_rate,
                'srsd_identification_rate': srsd_fp.identification_rate,
                'improvement': baseline_fp.identification_rate - srsd_fp.identification_rate,
            },
            'predictability': {
                'baseline_entropy': baseline_pred['entropy'],
                'srsd_entropy': srsd_pred['entropy'],
                'entropy_improvement': srsd_pred['entropy'] - baseline_pred['entropy'],
                'baseline_recurrence': baseline_pred['recurrence_rate'],
                'srsd_recurrence': srsd_pred['recurrence_rate'],
                'recurrence_reduction': baseline_pred['recurrence_rate'] - srsd_pred['recurrence_rate'],
            },
        }

    def get_summary(self) -> Dict:
        """Get summary of all metrics."""
        return {
            'baseline_flows': len(self._baseline_flows),
            'srsd_flows': len(self._srsd_flows),
            'comparison': self.compare_baseline_vs_srsd() if self._baseline_flows and self._srsd_flows else None,
        }

    def reset(self) -> None:
        """Reset collected data."""
        self._baseline_flows.clear()
        self._srsd_flows.clear()


def calculate_adversary_advantage(
    baseline_metrics: Dict,
    srsd_metrics: Dict
) -> Dict:
    """
    Calculate the adversary's advantage under baseline vs SRSD.

    Positive values indicate adversary has advantage under baseline.
    Negative values would indicate SRSD makes attack harder.

    Args:
        baseline_metrics: Metrics under baseline routing
        srsd_metrics: Metrics under SRSD routing

    Returns:
        Dictionary of advantage metrics
    """
    advantages = {}

    # Correlation advantage (higher correlation success = worse for defender)
    if 'correlation_accuracy' in baseline_metrics and 'correlation_accuracy' in srsd_metrics:
        advantages['correlation_advantage'] = (
            baseline_metrics['correlation_accuracy'] -
            srsd_metrics['correlation_accuracy']
        )

    # Entropy disadvantage for adversary (higher entropy = harder to attack)
    if 'entropy' in baseline_metrics and 'entropy' in srsd_metrics:
        advantages['entropy_disadvantage'] = (
            srsd_metrics['entropy'] - baseline_metrics['entropy']
        )

    # Recurrence advantage (higher recurrence = easier to attack)
    if 'recurrence_rate' in baseline_metrics and 'recurrence_rate' in srsd_metrics:
        advantages['recurrence_advantage'] = (
            baseline_metrics['recurrence_rate'] -
            srsd_metrics['recurrence_rate']
        )

    return advantages
