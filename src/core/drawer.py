"""
Drawer - Gateway de Encaminhamento Seguro.

Implements local routing decisions without global topology knowledge.
Each Drawer only knows its direct neighbors and makes forwarding decisions
based on local state only.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import random


@dataclass
class DrawerStatistics:
    """Statistics for Drawer operations."""

    selections_made: int = 0
    forced_unblocks: int = 0
    no_eligible_count: int = 0

    def record_selection(self) -> None:
        """Record a successful selection."""
        self.selections_made += 1

    def record_forced_unblock(self) -> None:
        """Record a forced unblock event."""
        self.forced_unblocks += 1

    def record_no_eligible(self) -> None:
        """Record when no eligible neighbors exist."""
        self.no_eligible_count += 1

    def reset(self) -> None:
        """Reset all statistics."""
        self.selections_made = 0
        self.forced_unblocks = 0
        self.no_eligible_count = 0


class Drawer:
    """
    Gateway de Encaminhamento Seguro - Local routing decisions.

    Key characteristics:
    - NO global topology knowledge (only knows direct neighbors)
    - BLOCKS (not penalizes) previously used neighbors for a destination
    - Forces unblock when all neighbors are blocked
    - Decisions are purely local
    """

    def __init__(self, node_id: str, neighbors: List[str],
                 blocking_window: int = 3, seed: Optional[int] = None):
        """
        Initialize Drawer.

        Args:
            node_id: ID of the node this Drawer belongs to
            neighbors: List of direct neighbor node IDs (ONLY local knowledge)
            blocking_window: Number of selections before automatic unblock
            seed: Random seed for reproducibility
        """
        self.node_id = node_id
        self.neighbors = list(neighbors)  # Copy to avoid external modification

        # Blocking state: destination -> set of blocked neighbors
        self.blocked: Dict[str, Set[str]] = {}

        # Block counter: (destination, neighbor) -> selection count
        self.block_counter: Dict[Tuple[str, str], int] = {}

        # Blocking window configuration
        self.blocking_window = blocking_window

        # Statistics
        self.stats = DrawerStatistics()

        # Random state
        self._rng = random.Random(seed)

    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._rng.seed(seed)

    def select_next_hop(self, destination: str) -> Optional[str]:
        """
        Select next hop for a destination WITHOUT global knowledge.

        This is the core SRSD mechanism:
        1. Get eligible neighbors (not blocked for this destination)
        2. If none eligible, force unblock the oldest
        3. Randomly select from eligible
        4. BLOCK the selected neighbor for this destination

        Args:
            destination: The segment destination (NOT the final destination)

        Returns:
            Selected neighbor ID, or None if no neighbors available
        """
        if not self.neighbors:
            self.stats.record_no_eligible()
            return None

        # Get eligible neighbors (not currently blocked for this destination)
        blocked_for_dest = self.blocked.get(destination, set())
        eligible = [n for n in self.neighbors if n not in blocked_for_dest]

        # If all blocked, force unblock
        if not eligible:
            self._force_unblock_oldest(destination)
            blocked_for_dest = self.blocked.get(destination, set())
            eligible = [n for n in self.neighbors if n not in blocked_for_dest]

        # Still no eligible after unblock (should not happen normally)
        if not eligible:
            self.stats.record_no_eligible()
            return None

        # Random selection from eligible neighbors
        selected = self._rng.choice(eligible)

        # BLOCK the selected neighbor (not penalize - complete block)
        self._block(destination, selected)

        self.stats.record_selection()
        return selected

    def _block(self, destination: str, neighbor: str) -> None:
        """
        BLOCK a neighbor for a destination.

        This is a hard block, not a penalty. The neighbor cannot be
        selected again for this destination until unblocked.
        """
        if destination not in self.blocked:
            self.blocked[destination] = set()

        self.blocked[destination].add(neighbor)

        # Track when this block was made
        key = (destination, neighbor)
        self.block_counter[key] = self.stats.selections_made

    def _force_unblock_oldest(self, destination: str) -> None:
        """
        Force unblock the oldest blocked neighbor for a destination.

        Called when all neighbors are blocked and we need to continue routing.
        """
        blocked_set = self.blocked.get(destination, set())
        if not blocked_set:
            return

        # Find the oldest blocked neighbor
        oldest_neighbor = None
        oldest_time = float('inf')

        for neighbor in blocked_set:
            key = (destination, neighbor)
            block_time = self.block_counter.get(key, 0)
            if block_time < oldest_time:
                oldest_time = block_time
                oldest_neighbor = neighbor

        if oldest_neighbor:
            blocked_set.discard(oldest_neighbor)
            key = (destination, oldest_neighbor)
            if key in self.block_counter:
                del self.block_counter[key]

            self.stats.record_forced_unblock()

    def unblock_all(self, destination: str) -> None:
        """
        Unblock all neighbors for a destination.

        Used when starting a new routing epoch or resetting state.
        """
        if destination in self.blocked:
            # Clean up block counters
            for neighbor in self.blocked[destination]:
                key = (destination, neighbor)
                if key in self.block_counter:
                    del self.block_counter[key]

            del self.blocked[destination]

    def decay_blocks(self) -> None:
        """
        Apply time-based decay to blocks.

        Unblocks neighbors that have been blocked for longer than
        the blocking window.
        """
        current_time = self.stats.selections_made
        to_unblock: List[Tuple[str, str]] = []

        for (dest, neighbor), block_time in self.block_counter.items():
            if current_time - block_time >= self.blocking_window:
                to_unblock.append((dest, neighbor))

        for dest, neighbor in to_unblock:
            if dest in self.blocked:
                self.blocked[dest].discard(neighbor)
                if not self.blocked[dest]:
                    del self.blocked[dest]

            key = (dest, neighbor)
            if key in self.block_counter:
                del self.block_counter[key]

    def get_blocked_count(self, destination: str) -> int:
        """Get number of blocked neighbors for a destination."""
        return len(self.blocked.get(destination, set()))

    def get_eligible_count(self, destination: str) -> int:
        """Get number of eligible (unblocked) neighbors for a destination."""
        blocked_count = self.get_blocked_count(destination)
        return len(self.neighbors) - blocked_count

    def reset(self) -> None:
        """Reset all Drawer state."""
        self.blocked.clear()
        self.block_counter.clear()
        self.stats.reset()

    def get_statistics(self) -> Dict:
        """Get Drawer statistics."""
        return {
            'node_id': self.node_id,
            'num_neighbors': len(self.neighbors),
            'selections_made': self.stats.selections_made,
            'forced_unblocks': self.stats.forced_unblocks,
            'no_eligible_count': self.stats.no_eligible_count,
            'active_blocks': sum(len(b) for b in self.blocked.values()),
        }


def initialize_drawers_from_graph(graph: 'NetworkGraph') -> Dict[str, Drawer]:
    """
    Initialize Drawers for all nodes in a graph.

    Args:
        graph: NetworkGraph instance

    Returns:
        Dictionary mapping node IDs to Drawer instances
    """
    drawers = {}

    for node in graph.get_nodes():
        neighbors = graph.get_neighbors(node.id)
        drawer = Drawer(node.id, neighbors)
        drawers[node.id] = drawer

    return drawers
