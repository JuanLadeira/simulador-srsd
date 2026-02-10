"""
Collector - Systematic metrics collection for experiments.

Collects, aggregates, and stores metrics during simulation runs.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import json
import time
import statistics


@dataclass
class TimeSeriesPoint:
    """Single point in a time series."""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricDefinition:
    """Definition of a metric to collect."""
    name: str
    description: str
    unit: str = ""
    aggregation: str = "mean"  # mean, sum, min, max, last
    labels: List[str] = field(default_factory=list)


class TimeSeries:
    """
    Time series data storage.

    Stores metric values over time with support for labels.
    """

    def __init__(self, name: str, unit: str = ""):
        """
        Initialize time series.

        Args:
            name: Metric name
            unit: Unit of measurement
        """
        self.name = name
        self.unit = unit
        self._points: List[TimeSeriesPoint] = []

    def add(self, value: float, timestamp: Optional[float] = None,
            labels: Optional[Dict[str, str]] = None) -> None:
        """Add a data point."""
        point = TimeSeriesPoint(
            timestamp=timestamp or time.time(),
            value=value,
            labels=labels or {},
        )
        self._points.append(point)

    def get_values(self) -> List[float]:
        """Get all values."""
        return [p.value for p in self._points]

    def get_timestamps(self) -> List[float]:
        """Get all timestamps."""
        return [p.timestamp for p in self._points]

    def get_points(self) -> List[TimeSeriesPoint]:
        """Get all points."""
        return self._points.copy()

    def filter_by_labels(self, labels: Dict[str, str]) -> 'TimeSeries':
        """Filter points by label values."""
        filtered = TimeSeries(self.name, self.unit)
        for point in self._points:
            if all(point.labels.get(k) == v for k, v in labels.items()):
                filtered._points.append(point)
        return filtered

    def aggregate(self, method: str = "mean") -> float:
        """
        Aggregate values.

        Args:
            method: Aggregation method (mean, sum, min, max, last, count)
        """
        values = self.get_values()
        if not values:
            return 0.0

        if method == "mean":
            return statistics.mean(values)
        elif method == "sum":
            return sum(values)
        elif method == "min":
            return min(values)
        elif method == "max":
            return max(values)
        elif method == "last":
            return values[-1]
        elif method == "count":
            return len(values)
        elif method == "stdev":
            return statistics.stdev(values) if len(values) > 1 else 0.0
        else:
            raise ValueError(f"Unknown aggregation method: {method}")

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'name': self.name,
            'unit': self.unit,
            'points': [
                {'timestamp': p.timestamp, 'value': p.value, 'labels': p.labels}
                for p in self._points
            ],
        }

    def __len__(self) -> int:
        return len(self._points)


class MetricsCollector:
    """
    Collects and manages metrics during simulation.

    Supports:
    - Time series metrics
    - Counter metrics
    - Gauge metrics
    - Histogram metrics
    """

    def __init__(self):
        """Initialize collector."""
        self._time_series: Dict[str, TimeSeries] = {}
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)

        # Metadata
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._metadata: Dict[str, Any] = {}

    def start(self) -> None:
        """Start collection (records start time)."""
        self._start_time = time.time()

    def stop(self) -> None:
        """Stop collection (records end time)."""
        self._end_time = time.time()

    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value."""
        self._metadata[key] = value

    # Time Series

    def record_ts(self, name: str, value: float,
                  timestamp: Optional[float] = None,
                  labels: Optional[Dict[str, str]] = None,
                  unit: str = "") -> None:
        """Record a time series value."""
        if name not in self._time_series:
            self._time_series[name] = TimeSeries(name, unit)

        self._time_series[name].add(value, timestamp, labels)

    def get_ts(self, name: str) -> Optional[TimeSeries]:
        """Get a time series."""
        return self._time_series.get(name)

    # Counters

    def inc_counter(self, name: str, value: float = 1.0) -> None:
        """Increment a counter."""
        self._counters[name] += value

    def get_counter(self, name: str) -> float:
        """Get counter value."""
        return self._counters.get(name, 0.0)

    # Gauges

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge value."""
        self._gauges[name] = value

    def get_gauge(self, name: str) -> float:
        """Get gauge value."""
        return self._gauges.get(name, 0.0)

    # Histograms

    def record_histogram(self, name: str, value: float) -> None:
        """Record a value in a histogram."""
        self._histograms[name].append(value)

    def get_histogram_stats(self, name: str) -> Dict:
        """Get statistics for a histogram."""
        values = self._histograms.get(name, [])
        if not values:
            return {
                'count': 0,
                'mean': 0.0,
                'min': 0.0,
                'max': 0.0,
                'stdev': 0.0,
                'p50': 0.0,
                'p95': 0.0,
                'p99': 0.0,
            }

        sorted_values = sorted(values)
        n = len(sorted_values)

        return {
            'count': n,
            'mean': statistics.mean(values),
            'min': min(values),
            'max': max(values),
            'stdev': statistics.stdev(values) if n > 1 else 0.0,
            'p50': sorted_values[int(n * 0.5)],
            'p95': sorted_values[int(n * 0.95)],
            'p99': sorted_values[int(n * 0.99)],
        }

    # Summary

    def get_summary(self) -> Dict:
        """Get summary of all collected metrics."""
        summary = {
            'metadata': self._metadata.copy(),
            'duration': (self._end_time - self._start_time) if self._start_time and self._end_time else None,
            'counters': dict(self._counters),
            'gauges': dict(self._gauges),
            'time_series': {},
            'histograms': {},
        }

        for name, ts in self._time_series.items():
            summary['time_series'][name] = {
                'count': len(ts),
                'mean': ts.aggregate('mean'),
                'min': ts.aggregate('min'),
                'max': ts.aggregate('max'),
            }

        for name in self._histograms:
            summary['histograms'][name] = self.get_histogram_stats(name)

        return summary

    def to_dict(self) -> dict:
        """Serialize all data to dictionary."""
        return {
            'metadata': self._metadata,
            'start_time': self._start_time,
            'end_time': self._end_time,
            'counters': dict(self._counters),
            'gauges': dict(self._gauges),
            'time_series': {
                name: ts.to_dict() for name, ts in self._time_series.items()
            },
            'histograms': dict(self._histograms),
        }

    def save(self, filepath: str) -> None:
        """Save all metrics to JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    def reset(self) -> None:
        """Reset all metrics."""
        self._time_series.clear()
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._start_time = None
        self._end_time = None
        self._metadata.clear()


class ExperimentMetrics:
    """
    Specialized metrics collector for SRSD experiments.

    Collects the specific metrics needed to validate H1 and H2.
    """

    def __init__(self):
        """Initialize experiment metrics."""
        self.collector = MetricsCollector()

        # Pre-define metrics
        self._define_metrics()

    def _define_metrics(self) -> None:
        """Define the metrics to collect."""
        self._metric_definitions = {
            # H1 metrics (predictability vulnerability)
            'path_entropy': MetricDefinition(
                name='path_entropy',
                description='Shannon entropy of path distribution',
                unit='bits',
                aggregation='mean',
            ),
            'route_repetition_rate': MetricDefinition(
                name='route_repetition_rate',
                description='Rate of route reuse',
                unit='ratio',
                aggregation='mean',
            ),
            'adversary_correlation': MetricDefinition(
                name='adversary_correlation',
                description='Adversary entry-exit correlation success',
                unit='ratio',
                aggregation='mean',
            ),

            # H2 metrics (SRSD effectiveness)
            'latency': MetricDefinition(
                name='latency',
                description='End-to-end latency',
                unit='ms',
                aggregation='mean',
            ),
            'overhead': MetricDefinition(
                name='overhead',
                description='Computational overhead',
                unit='ms',
                aggregation='mean',
            ),
            'success_rate': MetricDefinition(
                name='success_rate',
                description='Routing success rate',
                unit='ratio',
                aggregation='mean',
            ),
        }

    def start_experiment(self, experiment_name: str, **metadata) -> None:
        """Start collecting for an experiment."""
        self.collector.start()
        self.collector.set_metadata('experiment_name', experiment_name)
        self.collector.set_metadata('start_timestamp', datetime.now().isoformat())

        for key, value in metadata.items():
            self.collector.set_metadata(key, value)

    def end_experiment(self) -> None:
        """End experiment collection."""
        self.collector.stop()
        self.collector.set_metadata('end_timestamp', datetime.now().isoformat())

    def record_flow(self, algorithm: str, flow_latency: float,
                    flow_hops: int, success: bool) -> None:
        """Record metrics for a single flow."""
        labels = {'algorithm': algorithm}

        self.collector.record_ts('latency', flow_latency, labels=labels, unit='ms')
        self.collector.record_ts('hops', flow_hops, labels=labels)

        if success:
            self.collector.inc_counter(f'{algorithm}_successful_flows')
        else:
            self.collector.inc_counter(f'{algorithm}_failed_flows')

        self.collector.record_histogram(f'{algorithm}_latency', flow_latency)

    def record_path_entropy(self, algorithm: str, entropy: float) -> None:
        """Record path entropy."""
        self.collector.record_ts(
            'path_entropy', entropy,
            labels={'algorithm': algorithm},
            unit='bits'
        )
        self.collector.set_gauge(f'{algorithm}_path_entropy', entropy)

    def record_adversary_metrics(self, algorithm: str,
                                  correlation: float,
                                  identification: float) -> None:
        """Record adversary capability metrics."""
        labels = {'algorithm': algorithm}

        self.collector.record_ts('adversary_correlation', correlation, labels=labels)
        self.collector.record_ts('adversary_identification', identification, labels=labels)

        self.collector.set_gauge(f'{algorithm}_adversary_correlation', correlation)
        self.collector.set_gauge(f'{algorithm}_adversary_identification', identification)

    def record_overhead(self, algorithm: str, overhead_ms: float) -> None:
        """Record computational overhead."""
        self.collector.record_ts(
            'overhead', overhead_ms,
            labels={'algorithm': algorithm},
            unit='ms'
        )
        self.collector.record_histogram(f'{algorithm}_overhead', overhead_ms)

    def get_h1_validation_metrics(self) -> Dict:
        """Get metrics relevant to H1 validation."""
        metrics = {}

        for algo in ['baseline', 'srsd', 'srsd_qkd']:
            prefix = algo
            metrics[algo] = {
                'path_entropy': self.collector.get_gauge(f'{prefix}_path_entropy'),
                'adversary_correlation': self.collector.get_gauge(f'{prefix}_adversary_correlation'),
                'adversary_identification': self.collector.get_gauge(f'{prefix}_adversary_identification'),
            }

        return metrics

    def get_h2_validation_metrics(self) -> Dict:
        """Get metrics relevant to H2 validation."""
        metrics = {}

        for algo in ['baseline', 'srsd', 'srsd_qkd']:
            latency_stats = self.collector.get_histogram_stats(f'{algo}_latency')
            overhead_stats = self.collector.get_histogram_stats(f'{algo}_overhead')

            successful = self.collector.get_counter(f'{algo}_successful_flows')
            failed = self.collector.get_counter(f'{algo}_failed_flows')
            total = successful + failed

            metrics[algo] = {
                'latency_mean': latency_stats['mean'],
                'latency_p95': latency_stats['p95'],
                'overhead_mean': overhead_stats['mean'],
                'success_rate': successful / total if total > 0 else 0.0,
            }

        return metrics

    def get_comparison(self) -> Dict:
        """Get comparative analysis between algorithms."""
        h1 = self.get_h1_validation_metrics()
        h2 = self.get_h2_validation_metrics()

        comparison = {
            'h1_validation': {},
            'h2_validation': {},
        }

        # H1: Compare entropy and adversary metrics
        if 'baseline' in h1 and 'srsd' in h1:
            baseline_entropy = h1['baseline']['path_entropy']
            srsd_entropy = h1['srsd']['path_entropy']

            comparison['h1_validation']['entropy_improvement'] = (
                srsd_entropy - baseline_entropy
            ) if baseline_entropy else 0.0

            baseline_corr = h1['baseline']['adversary_correlation']
            srsd_corr = h1['srsd']['adversary_correlation']

            comparison['h1_validation']['correlation_reduction'] = (
                baseline_corr - srsd_corr
            ) if baseline_corr else 0.0

        # H2: Compare performance metrics
        if 'baseline' in h2 and 'srsd' in h2:
            baseline_latency = h2['baseline']['latency_mean']
            srsd_latency = h2['srsd']['latency_mean']

            if baseline_latency > 0:
                comparison['h2_validation']['latency_overhead_pct'] = (
                    (srsd_latency - baseline_latency) / baseline_latency * 100
                )
            else:
                comparison['h2_validation']['latency_overhead_pct'] = 0.0

            comparison['h2_validation']['baseline_success_rate'] = h2['baseline']['success_rate']
            comparison['h2_validation']['srsd_success_rate'] = h2['srsd']['success_rate']

        return comparison

    def save(self, filepath: str) -> None:
        """Save metrics to file."""
        self.collector.save(filepath)
