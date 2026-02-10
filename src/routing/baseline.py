"""
Baseline routing - Deterministic conventional routing.

Implements shortest-path routing as the control condition for experiments.
This represents the vulnerability (H1) where predictable routing enables
adversarial analysis.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import time

from ..core.graph import NetworkGraph
from ..core.edge import Edge


@dataclass
class FlowRecord:
    """Record of a routed flow."""

    flow_id: str
    source: str
    destination: str
    path: List[str]
    timestamp: float
    latency: float = 0.0
    hops: int = 0

    def __post_init__(self):
        self.hops = len(self.path) - 1 if self.path else 0


@dataclass
class RoutingStatistics:
    """Statistics for routing performance."""

    total_flows: int = 0
    successful_routes: int = 0
    failed_routes: int = 0
    total_latency: float = 0.0
    total_hops: int = 0

    # Path reuse tracking
    path_usage: Dict[str, int] = field(default_factory=dict)
    flow_records: List[FlowRecord] = field(default_factory=list)

    def record_success(self, flow: FlowRecord) -> None:
        """Record a successful route."""
        self.total_flows += 1
        self.successful_routes += 1
        self.total_latency += flow.latency
        self.total_hops += flow.hops
        self.flow_records.append(flow)

        # Track path usage
        path_key = '->'.join(flow.path)
        self.path_usage[path_key] = self.path_usage.get(path_key, 0) + 1

    def record_failure(self) -> None:
        """Record a failed route."""
        self.total_flows += 1
        self.failed_routes += 1

    @property
    def success_rate(self) -> float:
        """Calculate routing success rate."""
        if self.total_flows == 0:
            return 0.0
        return self.successful_routes / self.total_flows

    @property
    def avg_latency(self) -> float:
        """Calculate average latency."""
        if self.successful_routes == 0:
            return 0.0
        return self.total_latency / self.successful_routes

    @property
    def avg_hops(self) -> float:
        """Calculate average hop count."""
        if self.successful_routes == 0:
            return 0.0
        return self.total_hops / self.successful_routes

    @property
    def path_reuse_rate(self) -> float:
        """Calculate how often paths are reused."""
        if not self.path_usage:
            return 0.0
        total_uses = sum(self.path_usage.values())
        unique_paths = len(self.path_usage)
        if unique_paths == 0:
            return 0.0
        return total_uses / unique_paths

    @property
    def unique_paths(self) -> int:
        """Number of unique paths used."""
        return len(self.path_usage)

    def reset(self) -> None:
        """Reset all statistics."""
        self.total_flows = 0
        self.successful_routes = 0
        self.failed_routes = 0
        self.total_latency = 0.0
        self.total_hops = 0
        self.path_usage = {}
        self.flow_records = []

    def get_most_used_paths(self, n: int = 10) -> List[Tuple[str, int]]:
        """Get the n most frequently used paths."""
        sorted_paths = sorted(self.path_usage.items(), key=lambda x: x[1], reverse=True)
        return sorted_paths[:n]


class Router(ABC):
    """Abstract base class for routing algorithms."""

    def __init__(self, graph: NetworkGraph):
        """Initialize router with network graph."""
        self.graph = graph
        self.stats = RoutingStatistics()

    @abstractmethod
    def route(self, source: str, destination: str,
              flow_id: Optional[str] = None) -> Optional[FlowRecord]:
        """
        Route a flow from source to destination.

        Args:
            source: Source node ID
            destination: Destination node ID
            flow_id: Optional flow identifier

        Returns:
            FlowRecord if successful, None if no path exists
        """
        pass

    def reset(self) -> None:
        """Reset router state."""
        self.stats.reset()

    def get_statistics(self) -> RoutingStatistics:
        """Get routing statistics."""
        return self.stats


class BaselineRouter(Router):
    """
    Deterministic shortest-path routing.

    Always selects the same path for the same source-destination pair,
    making it predictable and vulnerable to adversarial analysis.
    """

    def __init__(self, graph: NetworkGraph, weight: str = 'weight'):
        """
        Initialize baseline router.

        Args:
            graph: Network graph
            weight: Edge attribute to use for path calculation
        """
        super().__init__(graph)
        self.weight = weight

        # Cache for computed paths (deterministic behavior)
        self._path_cache: Dict[Tuple[str, str], List[str]] = {}

    def route(self, source: str, destination: str,
              flow_id: Optional[str] = None) -> Optional[FlowRecord]:
        """
        Route using deterministic shortest path.

        Always returns the same path for the same source-destination pair.
        """
        timestamp = time.time()
        fid = flow_id or f"flow_{source}_{destination}_{timestamp}"

        # Check cache first (deterministic behavior)
        cache_key = (source, destination)
        if cache_key in self._path_cache:
            path = self._path_cache[cache_key]
        else:
            path = self.graph.shortest_path(source, destination, weight=self.weight)
            if path:
                self._path_cache[cache_key] = path

        if path is None:
            self.stats.record_failure()
            return None

        # Calculate path metrics
        latency = self._calculate_latency(path)

        # Record edge usage
        self._record_path_usage(path, timestamp)

        # Create flow record
        flow = FlowRecord(
            flow_id=fid,
            source=source,
            destination=destination,
            path=path,
            timestamp=timestamp,
            latency=latency,
        )

        self.stats.record_success(flow)
        return flow

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

            # Update node statistics
            node = self.graph.get_node(path[i])
            if node:
                node.stats.record_forward()

    def clear_cache(self) -> None:
        """Clear the path cache."""
        self._path_cache.clear()

    def reset(self) -> None:
        """Reset router state including cache."""
        super().reset()
        self._path_cache.clear()


class MultiPathRouter(Router):
    """
    Router that can select from multiple shortest paths.

    Still deterministic but may use different paths with same cost.
    Used for comparison with SRSD.
    """

    def __init__(self, graph: NetworkGraph, k: int = 3, weight: str = 'weight'):
        """
        Initialize multi-path router.

        Args:
            graph: Network graph
            k: Number of alternative paths to consider
            weight: Edge attribute for path calculation
        """
        super().__init__(graph)
        self.k = k
        self.weight = weight

        # Cache multiple paths per source-destination pair
        self._paths_cache: Dict[Tuple[str, str], List[List[str]]] = {}
        self._current_index: Dict[Tuple[str, str], int] = {}

    def route(self, source: str, destination: str,
              flow_id: Optional[str] = None) -> Optional[FlowRecord]:
        """
        Route using one of k shortest paths (round-robin selection).
        """
        timestamp = time.time()
        fid = flow_id or f"flow_{source}_{destination}_{timestamp}"

        cache_key = (source, destination)

        # Get or compute paths
        if cache_key not in self._paths_cache:
            paths = self.graph.k_shortest_paths(source, destination, k=self.k, weight=self.weight)
            if not paths:
                self.stats.record_failure()
                return None
            self._paths_cache[cache_key] = paths
            self._current_index[cache_key] = 0

        paths = self._paths_cache[cache_key]
        if not paths:
            self.stats.record_failure()
            return None

        # Round-robin path selection
        idx = self._current_index[cache_key]
        path = paths[idx % len(paths)]
        self._current_index[cache_key] = (idx + 1) % len(paths)

        # Calculate metrics
        latency = self._calculate_latency(path)

        # Record usage
        self._record_path_usage(path, timestamp)

        flow = FlowRecord(
            flow_id=fid,
            source=source,
            destination=destination,
            path=path,
            timestamp=timestamp,
            latency=latency,
        )

        self.stats.record_success(flow)
        return flow

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

    def reset(self) -> None:
        """Reset router state."""
        super().reset()
        self._paths_cache.clear()
        self._current_index.clear()
