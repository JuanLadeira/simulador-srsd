"""
Route Memory - Structural memory for SRSD routing.

Maintains history of used paths to enable non-repetitive routing
and penalize frequently used routes.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import time
import math


@dataclass
class PathEntry:
    """Entry in the route memory for a specific path."""

    path: Tuple[str, ...]
    usage_count: int = 0
    last_used: Optional[float] = None
    first_used: Optional[float] = None
    usage_timestamps: List[float] = field(default_factory=list)

    def record_usage(self, timestamp: Optional[float] = None) -> None:
        """Record that this path was used."""
        ts = timestamp or time.time()
        self.usage_count += 1
        self.last_used = ts
        if self.first_used is None:
            self.first_used = ts
        self.usage_timestamps.append(ts)

    def get_recency(self, current_time: Optional[float] = None) -> float:
        """
        Get recency score (0-1).
        Higher means more recently used.
        """
        if self.last_used is None:
            return 0.0

        now = current_time or time.time()
        age = now - self.last_used

        # Exponential decay with 1-hour half-life
        half_life = 3600.0
        return math.exp(-age * math.log(2) / half_life)

    def get_frequency(self, window: float = 3600.0,
                      current_time: Optional[float] = None) -> float:
        """
        Get usage frequency in the given time window.

        Args:
            window: Time window in seconds
            current_time: Current timestamp

        Returns:
            Usage frequency (uses per second)
        """
        now = current_time or time.time()
        cutoff = now - window

        recent_uses = sum(1 for ts in self.usage_timestamps if ts >= cutoff)
        return recent_uses / window if window > 0 else 0.0


class RouteMemory:
    """
    Structural memory for tracking route usage patterns.

    Enables SRSD to:
    - Avoid recently used paths
    - Penalize frequently used edges
    - Favor structural diversity
    """

    def __init__(self,
                 recency_weight: float = 0.5,
                 frequency_weight: float = 0.5,
                 decay_rate: float = 0.1,
                 window_size: float = 3600.0):
        """
        Initialize route memory.

        Args:
            recency_weight: Weight for recency in penalty calculation
            frequency_weight: Weight for frequency in penalty calculation
            decay_rate: Rate at which old usage decays
            window_size: Time window for frequency calculation (seconds)
        """
        self.recency_weight = recency_weight
        self.frequency_weight = frequency_weight
        self.decay_rate = decay_rate
        self.window_size = window_size

        # Path-level memory
        self._path_memory: Dict[Tuple[str, str], Dict[Tuple[str, ...], PathEntry]] = defaultdict(dict)

        # Edge-level usage tracking
        self._edge_usage: Dict[str, PathEntry] = {}

        # Flow-specific memory (for per-flow diversity)
        self._flow_paths: Dict[str, List[Tuple[str, ...]]] = defaultdict(list)

    def record_path(self, source: str, destination: str,
                    path: List[str],
                    flow_id: Optional[str] = None,
                    timestamp: Optional[float] = None) -> None:
        """
        Record that a path was used.

        Args:
            source: Source node
            destination: Destination node
            path: List of node IDs in the path
            flow_id: Optional flow identifier
            timestamp: Optional timestamp
        """
        ts = timestamp or time.time()
        path_tuple = tuple(path)
        pair_key = (source, destination)

        # Record in path memory
        if path_tuple not in self._path_memory[pair_key]:
            self._path_memory[pair_key][path_tuple] = PathEntry(path=path_tuple)
        self._path_memory[pair_key][path_tuple].record_usage(ts)

        # Record edge usage
        for i in range(len(path) - 1):
            edge_id = f"{path[i]}->{path[i + 1]}"
            if edge_id not in self._edge_usage:
                self._edge_usage[edge_id] = PathEntry(path=(edge_id,))
            self._edge_usage[edge_id].record_usage(ts)

        # Record for flow-specific tracking
        if flow_id:
            self._flow_paths[flow_id].append(path_tuple)

    def get_path_penalty(self, source: str, destination: str,
                         path: List[str],
                         current_time: Optional[float] = None) -> float:
        """
        Calculate penalty for using a given path.

        Higher penalty means less desirable (more repeated).

        Args:
            source: Source node
            destination: Destination node
            path: Candidate path
            current_time: Current timestamp

        Returns:
            Penalty score (0 = no penalty, higher = more penalty)
        """
        now = current_time or time.time()
        path_tuple = tuple(path)
        pair_key = (source, destination)

        # Base penalty from path memory
        path_penalty = 0.0
        if path_tuple in self._path_memory[pair_key]:
            entry = self._path_memory[pair_key][path_tuple]
            recency = entry.get_recency(now)
            frequency = entry.get_frequency(self.window_size, now) * self.window_size  # Normalize

            path_penalty = (
                self.recency_weight * recency +
                self.frequency_weight * min(1.0, frequency)
            )

        # Additional penalty from edge usage
        edge_penalty = 0.0
        if len(path) > 1:
            for i in range(len(path) - 1):
                edge_id = f"{path[i]}->{path[i + 1]}"
                if edge_id in self._edge_usage:
                    entry = self._edge_usage[edge_id]
                    edge_penalty += entry.get_recency(now) * 0.1

            edge_penalty /= (len(path) - 1)  # Normalize by path length

        return path_penalty + edge_penalty

    def get_edge_penalty(self, source: str, target: str,
                         current_time: Optional[float] = None) -> float:
        """
        Get penalty for a specific edge.

        Args:
            source: Source node of edge
            target: Target node of edge
            current_time: Current timestamp

        Returns:
            Edge penalty score
        """
        now = current_time or time.time()
        edge_id = f"{source}->{target}"

        if edge_id not in self._edge_usage:
            return 0.0

        entry = self._edge_usage[edge_id]
        recency = entry.get_recency(now)
        frequency = entry.get_frequency(self.window_size, now) * self.window_size

        return (
            self.recency_weight * recency +
            self.frequency_weight * min(1.0, frequency)
        )

    def get_flow_diversity(self, flow_id: str) -> float:
        """
        Calculate path diversity for a specific flow.

        Returns ratio of unique paths to total paths (0-1).
        Higher means more diverse routing.
        """
        if flow_id not in self._flow_paths:
            return 1.0

        paths = self._flow_paths[flow_id]
        if len(paths) == 0:
            return 1.0

        unique_paths = len(set(paths))
        return unique_paths / len(paths)

    def get_used_paths(self, source: str, destination: str) -> List[Tuple[str, ...]]:
        """Get list of paths used for a source-destination pair."""
        pair_key = (source, destination)
        return list(self._path_memory[pair_key].keys())

    def get_path_statistics(self, source: str, destination: str) -> Dict:
        """Get statistics about paths for a source-destination pair."""
        pair_key = (source, destination)
        paths = self._path_memory[pair_key]

        if not paths:
            return {
                'unique_paths': 0,
                'total_uses': 0,
                'avg_uses_per_path': 0.0,
                'most_used_count': 0,
            }

        total_uses = sum(entry.usage_count for entry in paths.values())
        most_used = max(entry.usage_count for entry in paths.values())

        return {
            'unique_paths': len(paths),
            'total_uses': total_uses,
            'avg_uses_per_path': total_uses / len(paths) if paths else 0.0,
            'most_used_count': most_used,
        }

    def get_overall_statistics(self) -> Dict:
        """Get overall memory statistics."""
        total_pairs = len(self._path_memory)
        total_paths = sum(len(paths) for paths in self._path_memory.values())
        total_uses = sum(
            entry.usage_count
            for paths in self._path_memory.values()
            for entry in paths.values()
        )

        return {
            'source_dest_pairs': total_pairs,
            'unique_paths': total_paths,
            'total_path_uses': total_uses,
            'unique_edges_used': len(self._edge_usage),
            'tracked_flows': len(self._flow_paths),
        }

    def decay_memory(self, factor: Optional[float] = None) -> None:
        """
        Apply decay to memory entries.

        Reduces the influence of old usage patterns.
        """
        decay = factor or self.decay_rate

        # Remove old timestamps from path entries
        now = time.time()
        cutoff = now - self.window_size * 2  # Keep 2x window

        for paths in self._path_memory.values():
            for entry in paths.values():
                entry.usage_timestamps = [
                    ts for ts in entry.usage_timestamps if ts > cutoff
                ]

        for entry in self._edge_usage.values():
            entry.usage_timestamps = [
                ts for ts in entry.usage_timestamps if ts > cutoff
            ]

    def clear(self) -> None:
        """Clear all memory."""
        self._path_memory.clear()
        self._edge_usage.clear()
        self._flow_paths.clear()

    def clear_pair(self, source: str, destination: str) -> None:
        """Clear memory for a specific source-destination pair."""
        pair_key = (source, destination)
        if pair_key in self._path_memory:
            del self._path_memory[pair_key]


class AdversaryObservableMemory(RouteMemory):
    """
    Extended route memory that tracks what an adversary could observe.

    Separates internal routing decisions from externally observable patterns.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # What the adversary has observed
        self._observed_entry_exit: List[Tuple[str, str, float]] = []
        self._observed_timing: List[Tuple[str, float]] = []

    def record_observation(self, entry_node: str, exit_node: str,
                           timestamp: Optional[float] = None) -> None:
        """Record what an adversary at network edges would observe."""
        ts = timestamp or time.time()
        self._observed_entry_exit.append((entry_node, exit_node, ts))

    def record_timing_observation(self, node: str,
                                  timestamp: Optional[float] = None) -> None:
        """Record timing observation at a specific node."""
        ts = timestamp or time.time()
        self._observed_timing.append((node, ts))

    def get_observable_patterns(self) -> Dict:
        """Get patterns that would be visible to an adversary."""
        if not self._observed_entry_exit:
            return {'correlations': {}, 'frequency': {}}

        # Count entry-exit correlations
        correlations: Dict[Tuple[str, str], int] = defaultdict(int)
        for entry, exit_, _ in self._observed_entry_exit:
            correlations[(entry, exit_)] += 1

        # Calculate frequencies
        total = len(self._observed_entry_exit)
        frequencies = {
            pair: count / total
            for pair, count in correlations.items()
        }

        return {
            'correlations': dict(correlations),
            'frequency': frequencies,
            'total_observations': total,
        }

    def clear_observations(self) -> None:
        """Clear adversary observations."""
        self._observed_entry_exit.clear()
        self._observed_timing.clear()
