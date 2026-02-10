"""
Graph module - Network modeling as directed graph.

Provides the core network representation using NetworkX for graph operations
with custom Node and Edge classes for domain-specific attributes.
"""

import json
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple, Set
import networkx as nx
import numpy as np

from .node import Node, NodeType, NodeState
from .edge import Edge, EdgeAttributes


class NetworkGraph:
    """
    Directed graph representing a network topology.

    Wraps NetworkX DiGraph with domain-specific Node and Edge objects
    for routing simulation.
    """

    def __init__(self, name: str = "network"):
        """Initialize an empty network graph."""
        self.name = name
        self._graph = nx.DiGraph()
        self._nodes: Dict[str, Node] = {}
        self._edges: Dict[str, Edge] = {}

    @property
    def num_nodes(self) -> int:
        """Number of nodes in the network."""
        return len(self._nodes)

    @property
    def num_edges(self) -> int:
        """Number of edges in the network."""
        return len(self._edges)

    def add_node(self, node: Node) -> None:
        """Add a node to the network."""
        self._nodes[node.id] = node
        self._graph.add_node(node.id)

    def add_node_simple(self, node_id: str,
                        node_type: NodeType = NodeType.ROUTER,
                        x: float = 0.0, y: float = 0.0) -> Node:
        """Create and add a simple node."""
        node = Node(id=node_id, node_type=node_type, x=x, y=y)
        self.add_node(node)
        return node

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its edges."""
        if node_id not in self._nodes:
            return

        # Remove associated edges
        edges_to_remove = []
        for edge_id, edge in self._edges.items():
            if edge.source == node_id or edge.target == node_id:
                edges_to_remove.append(edge_id)

        for edge_id in edges_to_remove:
            del self._edges[edge_id]

        del self._nodes[node_id]
        self._graph.remove_node(node_id)

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_nodes(self) -> List[Node]:
        """Get all nodes."""
        return list(self._nodes.values())

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the network."""
        if edge.source not in self._nodes or edge.target not in self._nodes:
            raise ValueError(f"Source or target node not found for edge {edge.id}")

        self._edges[edge.id] = edge
        self._graph.add_edge(
            edge.source, edge.target,
            weight=edge.attributes.weight,
            latency=edge.attributes.latency,
        )

        # Update node edge references
        self._nodes[edge.source].add_outgoing_edge(edge.id)
        self._nodes[edge.target].add_incoming_edge(edge.id)

    def add_edge_simple(self, source: str, target: str,
                        weight: float = 1.0,
                        latency: float = 1.0,
                        bidirectional: bool = False) -> Edge:
        """Create and add a simple edge."""
        attrs = EdgeAttributes(weight=weight, latency=latency)
        edge = Edge(source=source, target=target, attributes=attrs)
        self.add_edge(edge)

        if bidirectional:
            reverse_attrs = EdgeAttributes(weight=weight, latency=latency)
            reverse_edge = Edge(source=target, target=source, attributes=reverse_attrs)
            self.add_edge(reverse_edge)

        return edge

    def remove_edge(self, edge_id: str) -> None:
        """Remove an edge from the network."""
        if edge_id not in self._edges:
            return

        edge = self._edges[edge_id]

        # Update node references
        if edge.source in self._nodes:
            self._nodes[edge.source].remove_outgoing_edge(edge_id)
        if edge.target in self._nodes:
            self._nodes[edge.target].remove_incoming_edge(edge_id)

        del self._edges[edge_id]
        if self._graph.has_edge(edge.source, edge.target):
            self._graph.remove_edge(edge.source, edge.target)

    def get_edge(self, edge_id: str) -> Optional[Edge]:
        """Get an edge by ID."""
        return self._edges.get(edge_id)

    def get_edge_between(self, source: str, target: str) -> Optional[Edge]:
        """Get edge between two nodes."""
        edge_id = f"{source}->{target}"
        return self._edges.get(edge_id)

    def get_edges(self) -> List[Edge]:
        """Get all edges."""
        return list(self._edges.values())

    def get_outgoing_edges(self, node_id: str) -> List[Edge]:
        """Get all outgoing edges from a node."""
        node = self._nodes.get(node_id)
        if not node:
            return []
        return [self._edges[eid] for eid in node.outgoing_edges if eid in self._edges]

    def get_incoming_edges(self, node_id: str) -> List[Edge]:
        """Get all incoming edges to a node."""
        node = self._nodes.get(node_id)
        if not node:
            return []
        return [self._edges[eid] for eid in node.incoming_edges if eid in self._edges]

    def get_neighbors(self, node_id: str) -> List[str]:
        """Get neighbor node IDs."""
        return list(self._graph.successors(node_id))

    def get_predecessors(self, node_id: str) -> List[str]:
        """Get predecessor node IDs."""
        return list(self._graph.predecessors(node_id))

    def has_path(self, source: str, target: str) -> bool:
        """Check if a path exists between two nodes."""
        return nx.has_path(self._graph, source, target)

    def shortest_path(self, source: str, target: str,
                      weight: str = 'weight') -> Optional[List[str]]:
        """Find shortest path using Dijkstra's algorithm."""
        try:
            return nx.shortest_path(self._graph, source, target, weight=weight)
        except nx.NetworkXNoPath:
            return None

    def all_simple_paths(self, source: str, target: str,
                         cutoff: Optional[int] = None) -> Iterator[List[str]]:
        """Generate all simple paths between two nodes."""
        return nx.all_simple_paths(self._graph, source, target, cutoff=cutoff)

    def k_shortest_paths(self, source: str, target: str,
                         k: int = 3, weight: str = 'weight') -> List[List[str]]:
        """Find k shortest paths (may include same-length paths)."""
        try:
            paths = list(nx.shortest_simple_paths(self._graph, source, target, weight=weight))
            return paths[:k]
        except nx.NetworkXNoPath:
            return []

    def path_length(self, path: List[str], weight: str = 'weight') -> float:
        """Calculate total weight of a path."""
        if len(path) < 2:
            return 0.0

        total = 0.0
        for i in range(len(path) - 1):
            edge = self.get_edge_between(path[i], path[i + 1])
            if edge:
                if weight == 'weight':
                    total += edge.attributes.weight
                elif weight == 'latency':
                    total += edge.attributes.latency
                else:
                    total += getattr(edge.attributes, weight, 1.0)
        return total

    def path_edges(self, path: List[str]) -> List[Edge]:
        """Get edges along a path."""
        edges = []
        for i in range(len(path) - 1):
            edge = self.get_edge_between(path[i], path[i + 1])
            if edge:
                edges.append(edge)
        return edges

    def get_endpoints(self) -> List[Node]:
        """Get all endpoint nodes."""
        return [n for n in self._nodes.values() if n.node_type == NodeType.ENDPOINT]

    def get_qkd_nodes(self) -> List[Node]:
        """Get all QKD-enabled nodes."""
        return [n for n in self._nodes.values() if n.node_type == NodeType.QKD_ENABLED]

    def reset_statistics(self) -> None:
        """Reset all node and edge statistics."""
        for node in self._nodes.values():
            node.stats.reset()
        for edge in self._edges.values():
            edge.reset_usage()

    def get_adjacency_matrix(self) -> np.ndarray:
        """Get adjacency matrix as numpy array."""
        return nx.to_numpy_array(self._graph)

    def get_graph_metrics(self) -> Dict:
        """Calculate graph-level metrics."""
        metrics = {
            'num_nodes': self.num_nodes,
            'num_edges': self.num_edges,
            'density': nx.density(self._graph),
        }

        if self.num_nodes > 0:
            # Degree statistics
            in_degrees = [d for _, d in self._graph.in_degree()]
            out_degrees = [d for _, d in self._graph.out_degree()]

            metrics['avg_in_degree'] = np.mean(in_degrees) if in_degrees else 0
            metrics['avg_out_degree'] = np.mean(out_degrees) if out_degrees else 0
            metrics['max_in_degree'] = max(in_degrees) if in_degrees else 0
            metrics['max_out_degree'] = max(out_degrees) if out_degrees else 0

            # Connectivity
            if nx.is_strongly_connected(self._graph):
                metrics['diameter'] = nx.diameter(self._graph)
                metrics['avg_path_length'] = nx.average_shortest_path_length(self._graph)
            else:
                metrics['diameter'] = None
                metrics['avg_path_length'] = None
                metrics['num_strongly_connected_components'] = nx.number_strongly_connected_components(self._graph)

        return metrics

    def to_dict(self) -> dict:
        """Serialize graph to dictionary."""
        return {
            'name': self.name,
            'nodes': [node.to_dict() for node in self._nodes.values()],
            'edges': [edge.to_dict() for edge in self._edges.values()],
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NetworkGraph':
        """Deserialize graph from dictionary."""
        graph = cls(name=data.get('name', 'network'))

        # Add nodes first
        for node_data in data.get('nodes', []):
            node = Node.from_dict(node_data)
            graph.add_node(node)

        # Then add edges
        for edge_data in data.get('edges', []):
            edge = Edge.from_dict(edge_data)
            graph.add_edge(edge)

        return graph

    def save(self, filepath: str) -> None:
        """Save graph to JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> 'NetworkGraph':
        """Load graph from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    # Factory methods for common topologies

    @classmethod
    def create_mesh(cls, rows: int, cols: int, bidirectional: bool = True) -> 'NetworkGraph':
        """Create a mesh/grid topology."""
        graph = cls(name=f"mesh_{rows}x{cols}")

        # Create nodes
        for i in range(rows):
            for j in range(cols):
                node_id = f"n_{i}_{j}"
                x = j * 100
                y = i * 100
                graph.add_node_simple(node_id, x=x, y=y)

        # Create edges
        for i in range(rows):
            for j in range(cols):
                current = f"n_{i}_{j}"

                # Right neighbor
                if j < cols - 1:
                    right = f"n_{i}_{j+1}"
                    graph.add_edge_simple(current, right, bidirectional=bidirectional)

                # Bottom neighbor
                if i < rows - 1:
                    bottom = f"n_{i+1}_{j}"
                    graph.add_edge_simple(current, bottom, bidirectional=bidirectional)

        return graph

    @classmethod
    def create_barabasi_albert(cls, n: int, m: int, seed: int = None) -> 'NetworkGraph':
        """
        Create a scale-free network using Barabási-Albert model.

        Args:
            n: Number of nodes
            m: Number of edges to attach from new node to existing nodes
            seed: Random seed for reproducibility
        """
        nx_graph = nx.barabasi_albert_graph(n, m, seed=seed)
        graph = cls(name=f"barabasi_albert_{n}_{m}")

        # Add nodes with random positions
        rng = np.random.default_rng(seed)
        for node_id in nx_graph.nodes():
            x = rng.uniform(0, 1000)
            y = rng.uniform(0, 1000)
            graph.add_node_simple(f"n_{node_id}", x=x, y=y)

        # Add bidirectional edges
        for u, v in nx_graph.edges():
            graph.add_edge_simple(f"n_{u}", f"n_{v}", bidirectional=True)

        return graph

    @classmethod
    def create_watts_strogatz(cls, n: int, k: int, p: float,
                               seed: int = None) -> 'NetworkGraph':
        """
        Create a small-world network using Watts-Strogatz model.

        Args:
            n: Number of nodes
            k: Each node connected to k nearest neighbors
            p: Probability of rewiring each edge
            seed: Random seed for reproducibility
        """
        nx_graph = nx.watts_strogatz_graph(n, k, p, seed=seed)
        graph = cls(name=f"watts_strogatz_{n}_{k}_{p}")

        # Arrange nodes in a circle
        for i, node_id in enumerate(nx_graph.nodes()):
            angle = 2 * np.pi * i / n
            x = 500 + 400 * np.cos(angle)
            y = 500 + 400 * np.sin(angle)
            graph.add_node_simple(f"n_{node_id}", x=x, y=y)

        # Add bidirectional edges
        for u, v in nx_graph.edges():
            graph.add_edge_simple(f"n_{u}", f"n_{v}", bidirectional=True)

        return graph

    @classmethod
    def create_random(cls, n: int, p: float, seed: int = None) -> 'NetworkGraph':
        """
        Create an Erdős-Rényi random graph.

        Args:
            n: Number of nodes
            p: Probability of edge creation
            seed: Random seed for reproducibility
        """
        nx_graph = nx.erdos_renyi_graph(n, p, seed=seed, directed=True)
        graph = cls(name=f"random_{n}_{p}")

        rng = np.random.default_rng(seed)
        for node_id in nx_graph.nodes():
            x = rng.uniform(0, 1000)
            y = rng.uniform(0, 1000)
            graph.add_node_simple(f"n_{node_id}", x=x, y=y)

        for u, v in nx_graph.edges():
            graph.add_edge_simple(f"n_{u}", f"n_{v}")

        return graph

    def __repr__(self) -> str:
        return f"NetworkGraph(name='{self.name}', nodes={self.num_nodes}, edges={self.num_edges})"
