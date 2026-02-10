"""
Comparator - Comparative analysis of baseline vs SRSD.

Provides tools for comparing routing algorithms and generating
analysis reports.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import math

from ..simulation.runner import ExperimentResult, RunResult


@dataclass
class ComparisonResult:
    """Result of comparing two algorithms."""

    algorithm_a: str
    algorithm_b: str

    # Entropy comparison
    entropy_a: float = 0.0
    entropy_b: float = 0.0
    entropy_improvement: float = 0.0
    entropy_improvement_pct: float = 0.0

    # Path diversity
    unique_paths_a: int = 0
    unique_paths_b: int = 0
    diversity_improvement: float = 0.0

    # Performance
    latency_a: float = 0.0
    latency_b: float = 0.0
    latency_overhead: float = 0.0
    latency_overhead_pct: float = 0.0

    # Adversary resistance
    correlation_a: float = 0.0
    correlation_b: float = 0.0
    correlation_reduction: float = 0.0

    # Success rates
    success_rate_a: float = 0.0
    success_rate_b: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'algorithm_a': self.algorithm_a,
            'algorithm_b': self.algorithm_b,
            'entropy': {
                'a': self.entropy_a,
                'b': self.entropy_b,
                'improvement': self.entropy_improvement,
                'improvement_pct': self.entropy_improvement_pct,
            },
            'diversity': {
                'unique_paths_a': self.unique_paths_a,
                'unique_paths_b': self.unique_paths_b,
                'improvement': self.diversity_improvement,
            },
            'latency': {
                'a': self.latency_a,
                'b': self.latency_b,
                'overhead': self.latency_overhead,
                'overhead_pct': self.latency_overhead_pct,
            },
            'adversary': {
                'correlation_a': self.correlation_a,
                'correlation_b': self.correlation_b,
                'reduction': self.correlation_reduction,
            },
            'success_rate': {
                'a': self.success_rate_a,
                'b': self.success_rate_b,
            },
        }


class ResultComparator:
    """
    Compares results from different routing algorithms.

    Provides statistical analysis and visualization preparation.
    """

    def __init__(self):
        """Initialize comparator."""
        self._results: Dict[str, ExperimentResult] = {}

    def add_result(self, name: str, result: ExperimentResult) -> None:
        """Add an experiment result."""
        self._results[name] = result

    def load_result(self, name: str, filepath: str) -> None:
        """Load result from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        # Reconstruct ExperimentResult
        result = ExperimentResult(
            scenario_name=data['scenario_name'],
            timestamp=data['timestamp'],
            duration=data['duration'],
        )

        for algo_name, algo_data in data.get('results', {}).items():
            run_result = RunResult(
                algorithm=algo_data['algorithm'],
                flows=[],  # Not loading flows for efficiency
                total_time=algo_data['total_time'],
                successful_flows=algo_data['successful_flows'],
                failed_flows=algo_data['failed_flows'],
                avg_latency=algo_data['avg_latency'],
                avg_hops=algo_data['avg_hops'],
                path_entropy=algo_data['path_entropy'],
                unique_paths=algo_data['unique_paths'],
            )
            result.add_result(run_result)

        result.comparison = data.get('comparison', {})
        self._results[name] = result

    def compare(self, algorithm_a: str, algorithm_b: str,
                experiment: Optional[str] = None) -> Optional[ComparisonResult]:
        """
        Compare two algorithms from experiment results.

        Args:
            algorithm_a: First algorithm name (typically baseline)
            algorithm_b: Second algorithm name (typically SRSD)
            experiment: Specific experiment name (uses first if None)

        Returns:
            ComparisonResult or None if algorithms not found
        """
        if not self._results:
            return None

        exp_name = experiment or list(self._results.keys())[0]
        if exp_name not in self._results:
            return None

        exp = self._results[exp_name]

        if algorithm_a not in exp.results or algorithm_b not in exp.results:
            return None

        result_a = exp.results[algorithm_a]
        result_b = exp.results[algorithm_b]

        comparison = ComparisonResult(
            algorithm_a=algorithm_a,
            algorithm_b=algorithm_b,
        )

        # Entropy
        comparison.entropy_a = result_a.path_entropy
        comparison.entropy_b = result_b.path_entropy
        comparison.entropy_improvement = result_b.path_entropy - result_a.path_entropy

        if result_a.path_entropy > 0:
            comparison.entropy_improvement_pct = (
                comparison.entropy_improvement / result_a.path_entropy * 100
            )

        # Diversity
        comparison.unique_paths_a = result_a.unique_paths
        comparison.unique_paths_b = result_b.unique_paths
        if result_a.unique_paths > 0:
            comparison.diversity_improvement = (
                (result_b.unique_paths - result_a.unique_paths) /
                result_a.unique_paths * 100
            )

        # Latency
        comparison.latency_a = result_a.avg_latency
        comparison.latency_b = result_b.avg_latency
        comparison.latency_overhead = result_b.avg_latency - result_a.avg_latency

        if result_a.avg_latency > 0:
            comparison.latency_overhead_pct = (
                comparison.latency_overhead / result_a.avg_latency * 100
            )

        # Success rates
        total_a = result_a.successful_flows + result_a.failed_flows
        total_b = result_b.successful_flows + result_b.failed_flows

        comparison.success_rate_a = (
            result_a.successful_flows / total_a if total_a > 0 else 0.0
        )
        comparison.success_rate_b = (
            result_b.successful_flows / total_b if total_b > 0 else 0.0
        )

        return comparison

    def compare_all_experiments(self) -> Dict[str, ComparisonResult]:
        """Compare baseline vs SRSD across all experiments."""
        comparisons = {}

        for exp_name, exp in self._results.items():
            if 'baseline' in exp.results and 'srsd' in exp.results:
                comparison = self.compare('baseline', 'srsd', exp_name)
                if comparison:
                    comparisons[exp_name] = comparison

        return comparisons

    def aggregate_comparisons(self,
                              comparisons: Dict[str, ComparisonResult]) -> Dict:
        """
        Aggregate multiple comparisons into summary statistics.

        Args:
            comparisons: Dictionary of comparison results

        Returns:
            Aggregated statistics
        """
        if not comparisons:
            return {}

        entropy_improvements = []
        diversity_improvements = []
        latency_overheads = []
        success_rates_a = []
        success_rates_b = []

        for comp in comparisons.values():
            entropy_improvements.append(comp.entropy_improvement_pct)
            diversity_improvements.append(comp.diversity_improvement)
            latency_overheads.append(comp.latency_overhead_pct)
            success_rates_a.append(comp.success_rate_a)
            success_rates_b.append(comp.success_rate_b)

        def stats(values: List[float]) -> Dict:
            if not values:
                return {'mean': 0.0, 'min': 0.0, 'max': 0.0, 'stdev': 0.0}
            n = len(values)
            mean = sum(values) / n
            variance = sum((x - mean) ** 2 for x in values) / n if n > 1 else 0
            return {
                'mean': mean,
                'min': min(values),
                'max': max(values),
                'stdev': math.sqrt(variance),
            }

        return {
            'num_experiments': len(comparisons),
            'entropy_improvement_pct': stats(entropy_improvements),
            'diversity_improvement_pct': stats(diversity_improvements),
            'latency_overhead_pct': stats(latency_overheads),
            'baseline_success_rate': stats(success_rates_a),
            'srsd_success_rate': stats(success_rates_b),
        }

    def generate_report(self, output_path: Optional[str] = None) -> str:
        """
        Generate a text report of comparisons.

        Args:
            output_path: Optional path to save report

        Returns:
            Report text
        """
        lines = []
        lines.append("=" * 60)
        lines.append("SRSD Simulation Results Report")
        lines.append("=" * 60)
        lines.append("")

        comparisons = self.compare_all_experiments()
        aggregated = self.aggregate_comparisons(comparisons)

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Experiments analyzed: {aggregated.get('num_experiments', 0)}")
        lines.append("")

        if aggregated:
            lines.append("Entropy Improvement (Baseline -> SRSD):")
            ei = aggregated['entropy_improvement_pct']
            lines.append(f"  Mean: {ei['mean']:.2f}%")
            lines.append(f"  Range: {ei['min']:.2f}% - {ei['max']:.2f}%")
            lines.append("")

            lines.append("Path Diversity Improvement:")
            di = aggregated['diversity_improvement_pct']
            lines.append(f"  Mean: {di['mean']:.2f}%")
            lines.append(f"  Range: {di['min']:.2f}% - {di['max']:.2f}%")
            lines.append("")

            lines.append("Latency Overhead:")
            lo = aggregated['latency_overhead_pct']
            lines.append(f"  Mean: {lo['mean']:.2f}%")
            lines.append(f"  Range: {lo['min']:.2f}% - {lo['max']:.2f}%")
            lines.append("")

        # Per-experiment details
        lines.append("DETAILED RESULTS")
        lines.append("-" * 40)

        for exp_name, comp in comparisons.items():
            lines.append(f"\nExperiment: {exp_name}")
            lines.append(f"  Entropy: {comp.entropy_a:.4f} -> {comp.entropy_b:.4f} ({comp.entropy_improvement_pct:+.2f}%)")
            lines.append(f"  Unique Paths: {comp.unique_paths_a} -> {comp.unique_paths_b}")
            lines.append(f"  Latency: {comp.latency_a:.2f}ms -> {comp.latency_b:.2f}ms ({comp.latency_overhead_pct:+.2f}%)")
            lines.append(f"  Success Rate: {comp.success_rate_a:.2%} -> {comp.success_rate_b:.2%}")

        lines.append("")
        lines.append("=" * 60)

        report = "\n".join(lines)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                f.write(report)

        return report

    def prepare_visualization_data(self) -> Dict:
        """
        Prepare data for visualization (charts, plots).

        Returns:
            Dictionary with data formatted for common plotting libraries.
        """
        data = {
            'experiments': [],
            'baseline': {
                'entropy': [],
                'latency': [],
                'success_rate': [],
                'unique_paths': [],
            },
            'srsd': {
                'entropy': [],
                'latency': [],
                'success_rate': [],
                'unique_paths': [],
            },
            'improvement': {
                'entropy_pct': [],
                'diversity_pct': [],
                'latency_overhead_pct': [],
            },
        }

        comparisons = self.compare_all_experiments()

        for exp_name, comp in comparisons.items():
            data['experiments'].append(exp_name)

            data['baseline']['entropy'].append(comp.entropy_a)
            data['baseline']['latency'].append(comp.latency_a)
            data['baseline']['success_rate'].append(comp.success_rate_a)
            data['baseline']['unique_paths'].append(comp.unique_paths_a)

            data['srsd']['entropy'].append(comp.entropy_b)
            data['srsd']['latency'].append(comp.latency_b)
            data['srsd']['success_rate'].append(comp.success_rate_b)
            data['srsd']['unique_paths'].append(comp.unique_paths_b)

            data['improvement']['entropy_pct'].append(comp.entropy_improvement_pct)
            data['improvement']['diversity_pct'].append(comp.diversity_improvement)
            data['improvement']['latency_overhead_pct'].append(comp.latency_overhead_pct)

        return data


def statistical_significance(values_a: List[float], values_b: List[float],
                              alpha: float = 0.05) -> Dict:
    """
    Calculate statistical significance of difference between two groups.

    Uses a simple t-test approximation.

    Args:
        values_a: First group of values
        values_b: Second group of values
        alpha: Significance level

    Returns:
        Dictionary with test results
    """
    if len(values_a) < 2 or len(values_b) < 2:
        return {'significant': False, 'reason': 'Insufficient samples'}

    n_a, n_b = len(values_a), len(values_b)
    mean_a = sum(values_a) / n_a
    mean_b = sum(values_b) / n_b

    var_a = sum((x - mean_a) ** 2 for x in values_a) / (n_a - 1)
    var_b = sum((x - mean_b) ** 2 for x in values_b) / (n_b - 1)

    # Pooled standard error
    se = math.sqrt(var_a / n_a + var_b / n_b)

    if se == 0:
        return {
            'significant': mean_a != mean_b,
            't_statistic': float('inf') if mean_a != mean_b else 0,
            'mean_difference': mean_b - mean_a,
        }

    t_stat = (mean_b - mean_a) / se

    # Approximate critical value for two-tailed test
    # (simplified, should use proper t-distribution)
    df = n_a + n_b - 2
    if df < 30:
        critical = 2.0  # Approximation
    else:
        critical = 1.96  # Normal approximation

    significant = abs(t_stat) > critical

    return {
        'significant': significant,
        't_statistic': t_stat,
        'mean_difference': mean_b - mean_a,
        'mean_a': mean_a,
        'mean_b': mean_b,
        'degrees_of_freedom': df,
    }
