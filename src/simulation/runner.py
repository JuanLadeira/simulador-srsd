"""
Runner - Executes simulation experiments.

Orchestrates the simulation by:
- Setting up the environment
- Running routing algorithms
- Collecting metrics
- Managing timing
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
import json

from ..core.graph import NetworkGraph
from ..routing.baseline import BaselineRouter, FlowRecord
from ..routing.srsd import SRSDRouter, SRSDConfig, QKDIntegratedSRSDRouter
from ..adversary.observer import StructuralObserver
from ..adversary.metrics import AdversaryCapabilityMetrics
from ..qkd.channel import QKDChannelManager
from .scenario import Scenario
from .collector import MetricsCollector


@dataclass
class RunResult:
    """Results from a single routing algorithm run."""

    algorithm: str
    flows: List[FlowRecord]
    total_time: float
    successful_flows: int
    failed_flows: int

    # Performance metrics
    avg_latency: float = 0.0
    avg_hops: float = 0.0
    path_entropy: float = 0.0
    unique_paths: int = 0

    # Adversary metrics
    adversary_correlation: float = 0.0
    adversary_identification: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'algorithm': self.algorithm,
            'total_time': self.total_time,
            'successful_flows': self.successful_flows,
            'failed_flows': self.failed_flows,
            'avg_latency': self.avg_latency,
            'avg_hops': self.avg_hops,
            'path_entropy': self.path_entropy,
            'unique_paths': self.unique_paths,
            'adversary_correlation': self.adversary_correlation,
            'adversary_identification': self.adversary_identification,
        }


@dataclass
class ExperimentResult:
    """Complete results from an experiment."""

    scenario_name: str
    timestamp: str
    duration: float

    # Per-algorithm results
    results: Dict[str, RunResult] = field(default_factory=dict)

    # Comparative metrics
    comparison: Dict = field(default_factory=dict)

    # Raw data references
    data_files: Dict[str, str] = field(default_factory=dict)

    def add_result(self, result: RunResult) -> None:
        """Add a run result."""
        self.results[result.algorithm] = result

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'scenario_name': self.scenario_name,
            'timestamp': self.timestamp,
            'duration': self.duration,
            'results': {k: v.to_dict() for k, v in self.results.items()},
            'comparison': self.comparison,
            'data_files': self.data_files,
        }

    def save(self, filepath: str) -> None:
        """Save results to JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class SimulationRunner:
    """
    Executes simulation experiments.

    Handles:
    - Environment setup
    - Algorithm execution
    - Metrics collection
    - Result aggregation
    """

    def __init__(self, scenario: Scenario):
        """
        Initialize runner with scenario.

        Args:
            scenario: Scenario to execute
        """
        self.scenario = scenario

        # Build components
        self.graph: Optional[NetworkGraph] = None
        self.traffic_pairs: List[Tuple[str, str]] = []

        # Routers
        self.baseline_router: Optional[BaselineRouter] = None
        self.srsd_router: Optional[SRSDRouter] = None
        self.qkd_srsd_router: Optional[QKDIntegratedSRSDRouter] = None

        # QKD (if enabled)
        self.qkd_manager: Optional[QKDChannelManager] = None

        # Observation and metrics
        self.observer: Optional[StructuralObserver] = None
        self.adversary_metrics: Optional[AdversaryCapabilityMetrics] = None
        self.collector: Optional[MetricsCollector] = None

        # State
        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize all components."""
        # Build topology
        self.graph = self.scenario.build_topology()

        # Generate traffic
        self.traffic_pairs = self.scenario.generate_traffic_pairs(self.graph)

        # Initialize routers
        if self.scenario.experiment.test_baseline:
            self.baseline_router = BaselineRouter(self.graph)

        if self.scenario.experiment.test_srsd:
            config = SRSDConfig(
                # Legacy mode parameters
                k_paths=self.scenario.experiment.srsd_k_paths,
                recurrence_penalty=self.scenario.experiment.srsd_recurrence_penalty,
                selection_temperature=self.scenario.experiment.srsd_temperature,
                # Distributed mode parameters
                use_distributed=self.scenario.experiment.use_distributed_srsd,
                num_hiatus=self.scenario.experiment.num_hiatus,
                hiatus_placement=self.scenario.experiment.hiatus_placement,
                blocking_window=self.scenario.experiment.blocking_window,
                seed=self.scenario.experiment.seed,
            )
            self.srsd_router = SRSDRouter(self.graph, config)
            if self.scenario.experiment.seed:
                self.srsd_router.set_seed(self.scenario.experiment.seed)

        # Initialize QKD if enabled
        if self.scenario.topology.qkd_enabled:
            self._init_qkd()

        if self.scenario.experiment.test_srsd_qkd and self.qkd_manager:
            # Note: QKD should NOT influence routing per SRSD spec
            # QKDIntegratedSRSDRouter now sets use_qkd_indicators=False
            config = SRSDConfig(
                k_paths=self.scenario.experiment.srsd_k_paths,
                recurrence_penalty=self.scenario.experiment.srsd_recurrence_penalty,
                use_distributed=self.scenario.experiment.use_distributed_srsd,
                num_hiatus=self.scenario.experiment.num_hiatus,
                hiatus_placement=self.scenario.experiment.hiatus_placement,
                blocking_window=self.scenario.experiment.blocking_window,
                seed=self.scenario.experiment.seed,
            )
            self.qkd_srsd_router = QKDIntegratedSRSDRouter(
                self.graph, config, self.qkd_manager
            )

        # Initialize observation and metrics
        self.observer = StructuralObserver(self.graph)
        self.adversary_metrics = AdversaryCapabilityMetrics(self.graph)
        self.collector = MetricsCollector()

        self._is_initialized = True

    def _init_qkd(self) -> None:
        """Initialize QKD channels based on edge configuration."""
        self.qkd_manager = QKDChannelManager()

        for edge in self.graph.get_edges():
            if edge.attributes.qkd_enabled:
                self.qkd_manager.create_channel(
                    source=edge.source,
                    target=edge.target,
                    initial_key_rate=edge.attributes.qkd_key_rate,
                    initial_qber=edge.attributes.qkd_error_rate,
                )

    def run(self) -> ExperimentResult:
        """
        Run the complete experiment.

        Returns:
            ExperimentResult with all metrics
        """
        if not self._is_initialized:
            self.initialize()

        result = ExperimentResult(
            scenario_name=self.scenario.name,
            timestamp=datetime.now().isoformat(),
            duration=0.0,
        )

        start_time = time.time()

        # Run pre-hooks
        for hook in self.scenario.pre_run_hooks:
            hook(self)

        # Run baseline
        if self.baseline_router:
            baseline_result = self._run_algorithm(
                'baseline',
                self.baseline_router,
            )
            result.add_result(baseline_result)

            # Add flows to adversary metrics
            for flow in baseline_result.flows:
                self.adversary_metrics.add_baseline_flow(flow)

        # Reset graph statistics between runs
        self.graph.reset_statistics()

        # Run SRSD
        if self.srsd_router:
            srsd_result = self._run_algorithm(
                'srsd',
                self.srsd_router,
            )
            result.add_result(srsd_result)

            # Add flows to adversary metrics
            for flow in srsd_result.flows:
                self.adversary_metrics.add_srsd_flow(flow)

        # Reset graph statistics
        self.graph.reset_statistics()

        # Run QKD-integrated SRSD
        if self.qkd_srsd_router:
            qkd_result = self._run_algorithm(
                'srsd_qkd',
                self.qkd_srsd_router,
            )
            result.add_result(qkd_result)

        # Calculate comparative metrics
        result.comparison = self._calculate_comparison(result)

        # Run post-hooks
        for hook in self.scenario.post_run_hooks:
            hook(self, result)

        result.duration = time.time() - start_time

        return result

    def _run_algorithm(self, name: str, router) -> RunResult:
        """Run a single routing algorithm."""
        flows = []
        start_time = time.time()

        # Calculate timing
        num_flows = len(self.traffic_pairs)
        flow_interval = 1.0 / self.scenario.traffic.flow_rate

        simulation_time = 0.0

        for i, (src, dst) in enumerate(self.traffic_pairs):
            flow_id = f"{name}_flow_{i}"

            # Route the flow
            flow = router.route(src, dst, flow_id)

            if flow:
                flows.append(flow)

                # Record observation for adversary
                self.observer.observe_flow(flow)

            # Advance simulation time
            simulation_time += flow_interval

        total_time = time.time() - start_time

        # Calculate metrics
        successful = len(flows)
        failed = num_flows - successful

        avg_latency = sum(f.latency for f in flows) / successful if successful else 0.0
        avg_hops = sum(f.hops for f in flows) / successful if successful else 0.0

        # Path metrics
        stats = router.get_statistics()
        from ..adversary.metrics import calculate_path_entropy
        path_entropy = calculate_path_entropy(stats)

        return RunResult(
            algorithm=name,
            flows=flows,
            total_time=total_time,
            successful_flows=successful,
            failed_flows=failed,
            avg_latency=avg_latency,
            avg_hops=avg_hops,
            path_entropy=path_entropy,
            unique_paths=stats.unique_paths,
        )

    def _calculate_comparison(self, result: ExperimentResult) -> Dict:
        """Calculate comparative metrics between algorithms."""
        comparison = {}

        if 'baseline' in result.results and 'srsd' in result.results:
            baseline = result.results['baseline']
            srsd = result.results['srsd']

            # Entropy improvement
            if baseline.path_entropy > 0:
                entropy_improvement = (
                    (srsd.path_entropy - baseline.path_entropy) /
                    baseline.path_entropy * 100
                )
            else:
                entropy_improvement = 100.0 if srsd.path_entropy > 0 else 0.0

            # Path diversity improvement
            if baseline.unique_paths > 0:
                diversity_improvement = (
                    (srsd.unique_paths - baseline.unique_paths) /
                    baseline.unique_paths * 100
                )
            else:
                diversity_improvement = 0.0

            # Latency overhead
            if baseline.avg_latency > 0:
                latency_overhead = (
                    (srsd.avg_latency - baseline.avg_latency) /
                    baseline.avg_latency * 100
                )
            else:
                latency_overhead = 0.0

            comparison['baseline_vs_srsd'] = {
                'entropy_improvement_pct': entropy_improvement,
                'diversity_improvement_pct': diversity_improvement,
                'latency_overhead_pct': latency_overhead,
                'baseline_entropy': baseline.path_entropy,
                'srsd_entropy': srsd.path_entropy,
                'baseline_unique_paths': baseline.unique_paths,
                'srsd_unique_paths': srsd.unique_paths,
            }

            # Get adversary comparison
            if self.adversary_metrics:
                adv_comparison = self.adversary_metrics.compare_baseline_vs_srsd()
                comparison['adversary'] = adv_comparison

        return comparison

    def save_results(self, result: ExperimentResult,
                     output_dir: Optional[str] = None) -> str:
        """
        Save experiment results.

        Args:
            result: Experiment result to save
            output_dir: Output directory (defaults to scenario config)

        Returns:
            Path to saved result file
        """
        out_dir = output_dir or self.scenario.experiment.output_dir
        path = Path(out_dir)
        path.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.scenario.name}_{timestamp}.json"
        filepath = path / filename

        result.save(str(filepath))

        return str(filepath)


class BatchRunner:
    """
    Runs multiple scenarios in batch.

    Useful for parameter sweeps or comparing different configurations.
    """

    def __init__(self, scenarios: List[Scenario]):
        """
        Initialize batch runner.

        Args:
            scenarios: List of scenarios to run
        """
        self.scenarios = scenarios
        self.results: List[ExperimentResult] = []

    def run_all(self, parallel: bool = False) -> List[ExperimentResult]:
        """
        Run all scenarios.

        Args:
            parallel: Whether to run in parallel (not implemented)

        Returns:
            List of experiment results
        """
        self.results = []

        for scenario in self.scenarios:
            print(f"Running scenario: {scenario.name}")

            runner = SimulationRunner(scenario)
            result = runner.run()
            self.results.append(result)

            # Save individual result
            runner.save_results(result)

            print(f"  Completed in {result.duration:.2f}s")

        return self.results

    def get_summary(self) -> Dict:
        """Get summary of all results."""
        if not self.results:
            return {'scenarios': 0}

        summary = {
            'scenarios': len(self.results),
            'total_duration': sum(r.duration for r in self.results),
            'results': [],
        }

        for result in self.results:
            scenario_summary = {
                'name': result.scenario_name,
                'duration': result.duration,
                'algorithms': list(result.results.keys()),
            }

            if result.comparison:
                scenario_summary['comparison'] = result.comparison

            summary['results'].append(scenario_summary)

        return summary
