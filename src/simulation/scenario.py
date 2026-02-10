"""
Scenario - Defines simulation scenarios for experiments.

Scenarios encapsulate:
- Network topology
- Traffic patterns
- Experiment parameters
- Expected conditions
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import yaml
import json

from ..core.graph import NetworkGraph
from ..core.node import NodeType


class TopologyType(Enum):
    """Types of network topologies."""
    MESH = "mesh"
    BARABASI_ALBERT = "barabasi_albert"
    WATTS_STROGATZ = "watts_strogatz"
    RANDOM = "random"
    CUSTOM = "custom"


class TrafficPattern(Enum):
    """Types of traffic patterns."""
    UNIFORM = "uniform"           # Uniform random traffic
    HOTSPOT = "hotspot"           # Traffic concentrated on few nodes
    BURST = "burst"               # Bursty traffic patterns
    SEQUENTIAL = "sequential"     # Sequential source-destination pairs
    REALISTIC = "realistic"       # Realistic mix of patterns


@dataclass
class TopologyConfig:
    """Configuration for topology generation."""

    type: TopologyType = TopologyType.MESH
    num_nodes: int = 20
    parameters: Dict[str, Any] = field(default_factory=dict)

    # For mesh
    rows: int = 4
    cols: int = 5

    # For Barabasi-Albert
    ba_m: int = 2  # Edges per new node

    # For Watts-Strogatz
    ws_k: int = 4  # Neighbors
    ws_p: float = 0.1  # Rewiring probability

    # For random
    random_p: float = 0.3  # Edge probability

    # Common
    bidirectional: bool = True
    seed: Optional[int] = None

    # QKD configuration
    qkd_enabled: bool = False
    qkd_coverage: float = 0.5  # Fraction of edges with QKD


@dataclass
class TrafficConfig:
    """Configuration for traffic generation."""

    pattern: TrafficPattern = TrafficPattern.UNIFORM
    num_flows: int = 1000
    flow_rate: float = 10.0  # Flows per second

    # Pattern-specific
    hotspot_nodes: int = 3
    hotspot_concentration: float = 0.7
    burst_size: int = 10
    burst_interval: float = 1.0

    # Flow characteristics
    flow_duration: float = 0.0  # 0 = instant
    packet_size: int = 1500

    seed: Optional[int] = None


@dataclass
class ExperimentConfig:
    """Configuration for experiment execution."""

    name: str = "experiment"
    description: str = ""

    # Duration
    duration: float = 100.0  # Simulation time in seconds
    warmup: float = 10.0     # Warmup period (excluded from results)

    # Routing algorithms to test
    test_baseline: bool = True
    test_srsd: bool = True
    test_srsd_qkd: bool = False

    # SRSD parameters
    srsd_k_paths: int = 5
    srsd_recurrence_penalty: float = 2.0
    srsd_temperature: float = 1.0

    # Metrics collection
    collect_per_flow: bool = True
    collect_per_second: bool = True
    sample_rate: float = 1.0  # Fraction of flows to fully track

    # Output
    output_dir: str = "data/results"
    save_flows: bool = False

    seed: Optional[int] = None


@dataclass
class Scenario:
    """
    Complete scenario definition for an experiment.

    Combines topology, traffic, and experiment configuration.
    """

    name: str
    description: str = ""

    topology: TopologyConfig = field(default_factory=TopologyConfig)
    traffic: TrafficConfig = field(default_factory=TrafficConfig)
    experiment: ExperimentConfig = field(default_factory=ExperimentConfig)

    # Custom hooks
    pre_run_hooks: List[Callable] = field(default_factory=list)
    post_run_hooks: List[Callable] = field(default_factory=list)

    def build_topology(self) -> NetworkGraph:
        """Build the network topology based on configuration."""
        topo = self.topology

        if topo.type == TopologyType.MESH:
            graph = NetworkGraph.create_mesh(
                rows=topo.rows,
                cols=topo.cols,
                bidirectional=topo.bidirectional,
            )

        elif topo.type == TopologyType.BARABASI_ALBERT:
            graph = NetworkGraph.create_barabasi_albert(
                n=topo.num_nodes,
                m=topo.ba_m,
                seed=topo.seed,
            )

        elif topo.type == TopologyType.WATTS_STROGATZ:
            graph = NetworkGraph.create_watts_strogatz(
                n=topo.num_nodes,
                k=topo.ws_k,
                p=topo.ws_p,
                seed=topo.seed,
            )

        elif topo.type == TopologyType.RANDOM:
            graph = NetworkGraph.create_random(
                n=topo.num_nodes,
                p=topo.random_p,
                seed=topo.seed,
            )

        else:
            # Custom topology - should be loaded separately
            raise ValueError(f"Custom topology requires explicit graph loading")

        graph.name = self.name

        # Apply QKD configuration if enabled
        if topo.qkd_enabled:
            self._apply_qkd_config(graph)

        return graph

    def _apply_qkd_config(self, graph: NetworkGraph) -> None:
        """Apply QKD configuration to graph edges."""
        import random
        rng = random.Random(self.topology.seed)

        edges = graph.get_edges()
        num_qkd = int(len(edges) * self.topology.qkd_coverage)

        # Randomly select edges for QKD
        selected = rng.sample(edges, min(num_qkd, len(edges)))

        for edge in selected:
            edge.attributes.qkd_enabled = True
            edge.attributes.qkd_key_rate = rng.uniform(1000, 10000)
            edge.attributes.qkd_error_rate = rng.uniform(0.01, 0.05)

    def generate_traffic_pairs(self, graph: NetworkGraph) -> List[Tuple[str, str]]:
        """
        Generate source-destination pairs based on traffic pattern.

        Returns:
            List of (source, destination) tuples
        """
        import random
        rng = random.Random(self.traffic.seed)

        nodes = [n.id for n in graph.get_nodes()]
        pairs = []

        if self.traffic.pattern == TrafficPattern.UNIFORM:
            for _ in range(self.traffic.num_flows):
                src, dst = rng.sample(nodes, 2)
                pairs.append((src, dst))

        elif self.traffic.pattern == TrafficPattern.HOTSPOT:
            # Select hotspot nodes
            hotspots = rng.sample(nodes, min(self.traffic.hotspot_nodes, len(nodes)))

            for _ in range(self.traffic.num_flows):
                if rng.random() < self.traffic.hotspot_concentration:
                    # Traffic involving hotspot
                    if rng.random() < 0.5:
                        src = rng.choice(hotspots)
                        dst = rng.choice([n for n in nodes if n != src])
                    else:
                        dst = rng.choice(hotspots)
                        src = rng.choice([n for n in nodes if n != dst])
                else:
                    src, dst = rng.sample(nodes, 2)
                pairs.append((src, dst))

        elif self.traffic.pattern == TrafficPattern.SEQUENTIAL:
            # Sequential pairs for testing deterministic patterns
            for i in range(self.traffic.num_flows):
                src_idx = i % len(nodes)
                dst_idx = (i + 1) % len(nodes)
                pairs.append((nodes[src_idx], nodes[dst_idx]))

        elif self.traffic.pattern == TrafficPattern.BURST:
            # Generate bursts of traffic
            num_bursts = self.traffic.num_flows // self.traffic.burst_size
            for _ in range(num_bursts):
                # Each burst uses same source-destination
                src, dst = rng.sample(nodes, 2)
                for _ in range(self.traffic.burst_size):
                    pairs.append((src, dst))

        else:  # REALISTIC - mix of patterns
            # 40% uniform, 30% hotspot, 20% repeated, 10% burst
            uniform_count = int(self.traffic.num_flows * 0.4)
            hotspot_count = int(self.traffic.num_flows * 0.3)
            repeat_count = int(self.traffic.num_flows * 0.2)
            burst_count = self.traffic.num_flows - uniform_count - hotspot_count - repeat_count

            # Uniform
            for _ in range(uniform_count):
                src, dst = rng.sample(nodes, 2)
                pairs.append((src, dst))

            # Hotspot
            hotspots = rng.sample(nodes, min(3, len(nodes)))
            for _ in range(hotspot_count):
                src = rng.choice(hotspots)
                dst = rng.choice([n for n in nodes if n != src])
                pairs.append((src, dst))

            # Repeated (same pairs)
            repeat_pairs = [tuple(rng.sample(nodes, 2)) for _ in range(5)]
            for _ in range(repeat_count):
                pairs.append(rng.choice(repeat_pairs))

            # Burst
            burst_pair = tuple(rng.sample(nodes, 2))
            for _ in range(burst_count):
                pairs.append(burst_pair)

            rng.shuffle(pairs)

        return pairs

    def to_dict(self) -> dict:
        """Serialize scenario to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'topology': {
                'type': self.topology.type.value,
                'num_nodes': self.topology.num_nodes,
                'rows': self.topology.rows,
                'cols': self.topology.cols,
                'ba_m': self.topology.ba_m,
                'ws_k': self.topology.ws_k,
                'ws_p': self.topology.ws_p,
                'random_p': self.topology.random_p,
                'bidirectional': self.topology.bidirectional,
                'qkd_enabled': self.topology.qkd_enabled,
                'qkd_coverage': self.topology.qkd_coverage,
                'seed': self.topology.seed,
            },
            'traffic': {
                'pattern': self.traffic.pattern.value,
                'num_flows': self.traffic.num_flows,
                'flow_rate': self.traffic.flow_rate,
                'hotspot_nodes': self.traffic.hotspot_nodes,
                'hotspot_concentration': self.traffic.hotspot_concentration,
                'seed': self.traffic.seed,
            },
            'experiment': {
                'name': self.experiment.name,
                'description': self.experiment.description,
                'duration': self.experiment.duration,
                'warmup': self.experiment.warmup,
                'test_baseline': self.experiment.test_baseline,
                'test_srsd': self.experiment.test_srsd,
                'test_srsd_qkd': self.experiment.test_srsd_qkd,
                'srsd_k_paths': self.experiment.srsd_k_paths,
                'srsd_recurrence_penalty': self.experiment.srsd_recurrence_penalty,
                'output_dir': self.experiment.output_dir,
                'seed': self.experiment.seed,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Scenario':
        """Deserialize scenario from dictionary."""
        topo_data = data.get('topology', {})
        traffic_data = data.get('traffic', {})
        exp_data = data.get('experiment', {})

        topology = TopologyConfig(
            type=TopologyType(topo_data.get('type', 'mesh')),
            num_nodes=topo_data.get('num_nodes', 20),
            rows=topo_data.get('rows', 4),
            cols=topo_data.get('cols', 5),
            ba_m=topo_data.get('ba_m', 2),
            ws_k=topo_data.get('ws_k', 4),
            ws_p=topo_data.get('ws_p', 0.1),
            random_p=topo_data.get('random_p', 0.3),
            bidirectional=topo_data.get('bidirectional', True),
            qkd_enabled=topo_data.get('qkd_enabled', False),
            qkd_coverage=topo_data.get('qkd_coverage', 0.5),
            seed=topo_data.get('seed'),
        )

        traffic = TrafficConfig(
            pattern=TrafficPattern(traffic_data.get('pattern', 'uniform')),
            num_flows=traffic_data.get('num_flows', 1000),
            flow_rate=traffic_data.get('flow_rate', 10.0),
            hotspot_nodes=traffic_data.get('hotspot_nodes', 3),
            hotspot_concentration=traffic_data.get('hotspot_concentration', 0.7),
            seed=traffic_data.get('seed'),
        )

        experiment = ExperimentConfig(
            name=exp_data.get('name', 'experiment'),
            description=exp_data.get('description', ''),
            duration=exp_data.get('duration', 100.0),
            warmup=exp_data.get('warmup', 10.0),
            test_baseline=exp_data.get('test_baseline', True),
            test_srsd=exp_data.get('test_srsd', True),
            test_srsd_qkd=exp_data.get('test_srsd_qkd', False),
            srsd_k_paths=exp_data.get('srsd_k_paths', 5),
            srsd_recurrence_penalty=exp_data.get('srsd_recurrence_penalty', 2.0),
            output_dir=exp_data.get('output_dir', 'data/results'),
            seed=exp_data.get('seed'),
        )

        return cls(
            name=data.get('name', 'scenario'),
            description=data.get('description', ''),
            topology=topology,
            traffic=traffic,
            experiment=experiment,
        )

    def save(self, filepath: str) -> None:
        """Save scenario to YAML file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    @classmethod
    def load(cls, filepath: str) -> 'Scenario':
        """Load scenario from YAML file."""
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)


def create_default_scenarios() -> List[Scenario]:
    """Create a set of default scenarios for testing."""
    scenarios = []

    # Small mesh for basic testing
    scenarios.append(Scenario(
        name="small_mesh",
        description="Small 3x3 mesh network for basic testing",
        topology=TopologyConfig(
            type=TopologyType.MESH,
            rows=3,
            cols=3,
            seed=42,
        ),
        traffic=TrafficConfig(
            pattern=TrafficPattern.UNIFORM,
            num_flows=100,
            seed=42,
        ),
        experiment=ExperimentConfig(
            name="small_mesh_test",
            duration=10.0,
        ),
    ))

    # Medium scale-free network
    scenarios.append(Scenario(
        name="medium_scalefree",
        description="Medium Barabasi-Albert network (50 nodes)",
        topology=TopologyConfig(
            type=TopologyType.BARABASI_ALBERT,
            num_nodes=50,
            ba_m=3,
            seed=42,
        ),
        traffic=TrafficConfig(
            pattern=TrafficPattern.HOTSPOT,
            num_flows=1000,
            hotspot_nodes=5,
            seed=42,
        ),
        experiment=ExperimentConfig(
            name="scalefree_hotspot",
            duration=100.0,
            test_srsd=True,
        ),
    ))

    # Large network with QKD
    scenarios.append(Scenario(
        name="large_qkd",
        description="Large network with partial QKD coverage",
        topology=TopologyConfig(
            type=TopologyType.WATTS_STROGATZ,
            num_nodes=100,
            ws_k=6,
            ws_p=0.1,
            qkd_enabled=True,
            qkd_coverage=0.3,
            seed=42,
        ),
        traffic=TrafficConfig(
            pattern=TrafficPattern.REALISTIC,
            num_flows=5000,
            seed=42,
        ),
        experiment=ExperimentConfig(
            name="large_qkd_test",
            duration=300.0,
            test_srsd_qkd=True,
        ),
    ))

    return scenarios
