"""Tests for simulation framework."""

import pytest
from pathlib import Path
import tempfile

from src.simulation.scenario import (
    Scenario,
    TopologyConfig,
    TrafficConfig,
    ExperimentConfig,
    TopologyType,
    TrafficPattern,
    create_default_scenarios,
)
from src.simulation.runner import SimulationRunner
from src.simulation.collector import MetricsCollector, ExperimentMetrics


class TestScenario:
    """Tests for scenario configuration."""

    def test_scenario_creation(self):
        """Test basic scenario creation."""
        scenario = Scenario(
            name="test",
            description="Test scenario",
        )
        assert scenario.name == "test"
        assert scenario.topology is not None
        assert scenario.traffic is not None

    def test_topology_building(self):
        """Test building topology from scenario."""
        scenario = Scenario(
            name="mesh_test",
            topology=TopologyConfig(
                type=TopologyType.MESH,
                rows=3,
                cols=3,
            ),
        )

        graph = scenario.build_topology()
        assert graph.num_nodes == 9

    def test_traffic_generation(self):
        """Test generating traffic pairs."""
        scenario = Scenario(
            name="traffic_test",
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
        )

        graph = scenario.build_topology()
        pairs = scenario.generate_traffic_pairs(graph)

        assert len(pairs) == 100
        for src, dst in pairs:
            assert src != dst

    def test_hotspot_traffic(self):
        """Test hotspot traffic pattern."""
        scenario = Scenario(
            name="hotspot_test",
            topology=TopologyConfig(
                type=TopologyType.MESH,
                rows=4,
                cols=4,
            ),
            traffic=TrafficConfig(
                pattern=TrafficPattern.HOTSPOT,
                num_flows=100,
                hotspot_nodes=2,
                hotspot_concentration=0.8,
                seed=42,
            ),
        )

        graph = scenario.build_topology()
        pairs = scenario.generate_traffic_pairs(graph)

        # Count flows involving hotspots (can't directly verify, but check generation)
        assert len(pairs) == 100

    def test_scenario_serialization(self):
        """Test scenario serialization."""
        scenario = Scenario(
            name="serialize_test",
            description="Test serialization",
            topology=TopologyConfig(type=TopologyType.MESH, rows=2, cols=2),
            traffic=TrafficConfig(num_flows=50),
        )

        data = scenario.to_dict()
        restored = Scenario.from_dict(data)

        assert restored.name == scenario.name
        assert restored.topology.rows == scenario.topology.rows

    def test_default_scenarios(self):
        """Test default scenario creation."""
        scenarios = create_default_scenarios()
        assert len(scenarios) >= 1

        for scenario in scenarios:
            assert scenario.name is not None
            graph = scenario.build_topology()
            assert graph.num_nodes > 0


class TestSimulationRunner:
    """Tests for simulation runner."""

    @pytest.fixture
    def simple_scenario(self):
        """Create simple scenario for testing."""
        return Scenario(
            name="runner_test",
            topology=TopologyConfig(
                type=TopologyType.MESH,
                rows=3,
                cols=3,
                seed=42,
            ),
            traffic=TrafficConfig(
                pattern=TrafficPattern.UNIFORM,
                num_flows=50,
                seed=42,
            ),
            experiment=ExperimentConfig(
                duration=10.0,
                test_baseline=True,
                test_srsd=True,
            ),
        )

    def test_runner_initialization(self, simple_scenario):
        """Test runner initialization."""
        runner = SimulationRunner(simple_scenario)
        runner.initialize()

        assert runner.graph is not None
        assert runner.baseline_router is not None
        assert runner.srsd_router is not None
        assert len(runner.traffic_pairs) == 50

    def test_runner_execution(self, simple_scenario):
        """Test running simulation."""
        runner = SimulationRunner(simple_scenario)
        result = runner.run()

        assert result is not None
        assert 'baseline' in result.results
        assert 'srsd' in result.results

        baseline = result.results['baseline']
        assert baseline.successful_flows > 0

    def test_result_comparison(self, simple_scenario):
        """Test result comparison."""
        runner = SimulationRunner(simple_scenario)
        result = runner.run()

        assert result.comparison is not None
        if 'baseline_vs_srsd' in result.comparison:
            comp = result.comparison['baseline_vs_srsd']
            assert 'entropy_improvement_pct' in comp

    def test_result_saving(self, simple_scenario):
        """Test saving results to file."""
        runner = SimulationRunner(simple_scenario)
        result = runner.run()

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = runner.save_results(result, tmpdir)
            assert Path(filepath).exists()


class TestMetricsCollector:
    """Tests for metrics collection."""

    def test_time_series(self):
        """Test time series recording."""
        collector = MetricsCollector()

        for i in range(10):
            collector.record_ts("latency", float(i * 10))

        ts = collector.get_ts("latency")
        assert ts is not None
        assert len(ts) == 10
        assert ts.aggregate("mean") == 45.0

    def test_counters(self):
        """Test counter metrics."""
        collector = MetricsCollector()

        collector.inc_counter("flows")
        collector.inc_counter("flows")
        collector.inc_counter("flows", 3)

        assert collector.get_counter("flows") == 5

    def test_gauges(self):
        """Test gauge metrics."""
        collector = MetricsCollector()

        collector.set_gauge("entropy", 1.5)
        assert collector.get_gauge("entropy") == 1.5

        collector.set_gauge("entropy", 2.0)
        assert collector.get_gauge("entropy") == 2.0

    def test_histograms(self):
        """Test histogram metrics."""
        collector = MetricsCollector()

        for i in range(100):
            collector.record_histogram("latency", float(i))

        stats = collector.get_histogram_stats("latency")
        assert stats['count'] == 100
        assert stats['mean'] == 49.5
        assert stats['min'] == 0.0
        assert stats['max'] == 99.0

    def test_summary(self):
        """Test getting summary."""
        collector = MetricsCollector()
        collector.start()

        collector.inc_counter("test")
        collector.set_gauge("value", 1.0)
        collector.record_ts("metric", 10.0)

        collector.stop()
        summary = collector.get_summary()

        assert 'counters' in summary
        assert 'gauges' in summary
        assert 'time_series' in summary


class TestExperimentMetrics:
    """Tests for experiment-specific metrics."""

    def test_flow_recording(self):
        """Test recording flow metrics."""
        metrics = ExperimentMetrics()
        metrics.start_experiment("test")

        metrics.record_flow("baseline", 10.0, 3, True)
        metrics.record_flow("baseline", 15.0, 4, True)
        metrics.record_flow("baseline", 0.0, 0, False)

        metrics.end_experiment()

        summary = metrics.collector.get_summary()
        assert summary['counters']['baseline_successful_flows'] == 2
        assert summary['counters']['baseline_failed_flows'] == 1

    def test_h1_metrics(self):
        """Test H1 validation metrics."""
        metrics = ExperimentMetrics()
        metrics.start_experiment("test")

        metrics.record_path_entropy("baseline", 1.0)
        metrics.record_path_entropy("srsd", 2.0)

        h1 = metrics.get_h1_validation_metrics()
        assert h1['baseline']['path_entropy'] == 1.0
        assert h1['srsd']['path_entropy'] == 2.0

    def test_h2_metrics(self):
        """Test H2 validation metrics."""
        metrics = ExperimentMetrics()
        metrics.start_experiment("test")

        for _ in range(10):
            metrics.record_flow("baseline", 10.0, 3, True)
            metrics.record_flow("srsd", 12.0, 4, True)

        h2 = metrics.get_h2_validation_metrics()
        assert h2['baseline']['success_rate'] == 1.0
        assert h2['srsd']['success_rate'] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
