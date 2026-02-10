"""Tests for adversary modeling and metrics."""

import pytest

from src.core.graph import NetworkGraph
from src.routing.baseline import BaselineRouter, FlowRecord
from src.adversary.observer import StructuralObserver, TimingAnalyzer
from src.adversary.metrics import (
    AdversaryCapabilityMetrics,
    calculate_path_entropy,
    calculate_normalized_entropy,
    calculate_recurrence_rate,
)


class TestStructuralObserver:
    """Tests for structural adversary observer."""

    @pytest.fixture
    def graph_and_flows(self):
        """Create graph and sample flows."""
        graph = NetworkGraph.create_mesh(rows=3, cols=3)
        router = BaselineRouter(graph)

        flows = []
        for i in range(10):
            flow = router.route("n_0_0", "n_2_2", f"flow_{i}")
            if flow:
                flows.append(flow)

        return graph, flows

    def test_observer_creation(self, graph_and_flows):
        """Test observer initialization."""
        graph, _ = graph_and_flows
        observer = StructuralObserver(graph)

        assert observer.graph == graph
        assert len(observer.vantage_points) == graph.num_nodes

    def test_flow_observation(self, graph_and_flows):
        """Test observing flows."""
        graph, flows = graph_and_flows
        observer = StructuralObserver(graph)

        for flow in flows:
            observer.observe_flow(flow)

        stats = observer.get_observation_statistics()
        assert stats['unique_flows_observed'] == len(flows)

    def test_correlation_detection(self, graph_and_flows):
        """Test entry-exit correlation."""
        graph, flows = graph_and_flows
        observer = StructuralObserver(graph)

        for flow in flows:
            observer.observe_flow(flow)

        correlations = observer.correlate_entry_exit()
        assert len(correlations) > 0

    def test_recurring_flow_detection(self, graph_and_flows):
        """Test detection of recurring flows."""
        graph, flows = graph_and_flows
        observer = StructuralObserver(graph)

        for flow in flows:
            observer.observe_flow(flow)

        recurring = observer.identify_recurring_flows(min_occurrences=5)
        # All flows use same path, should be detected
        assert len(recurring) >= 1

    def test_limited_vantage_points(self, graph_and_flows):
        """Test observer with limited vantage points."""
        graph, flows = graph_and_flows

        # Only observe at edge nodes
        vantage_points = ["n_0_0", "n_2_2"]
        observer = StructuralObserver(graph, vantage_points=vantage_points)

        for flow in flows:
            observer.observe_flow(flow)

        stats = observer.get_observation_statistics()
        assert stats['vantage_point_coverage'] < 1.0


class TestTimingAnalyzer:
    """Tests for timing analysis."""

    def test_timing_recording(self):
        """Test timing observation recording."""
        analyzer = TimingAnalyzer()

        for i in range(10):
            analyzer.record_timing("node1", float(i))

        pattern = analyzer.get_timing_pattern("node1")
        assert pattern is not None
        assert pattern['sample_count'] == 9  # IAT count is n-1

    def test_periodicity_detection(self):
        """Test detection of periodic traffic."""
        analyzer = TimingAnalyzer()

        # Regular periodic traffic
        for i in range(20):
            analyzer.record_timing("node1", float(i * 0.1))

        period = analyzer.detect_periodicity("node1", tolerance=0.2)
        assert period is not None
        assert abs(period - 0.1) < 0.02


class TestAdversaryMetrics:
    """Tests for adversary capability metrics."""

    @pytest.fixture
    def flows_baseline_srsd(self):
        """Create flows from baseline and SRSD routing."""
        graph = NetworkGraph.create_mesh(rows=4, cols=4)

        # Baseline flows (deterministic)
        baseline_router = BaselineRouter(graph)
        baseline_flows = []
        for i in range(20):
            flow = baseline_router.route("n_0_0", "n_3_3", f"baseline_{i}")
            if flow:
                baseline_flows.append(flow)

        # SRSD flows (diverse)
        from src.routing.srsd import SRSDRouter, SRSDConfig
        config = SRSDConfig(k_paths=5, recurrence_penalty=2.0)
        srsd_router = SRSDRouter(graph, config)
        srsd_router.set_seed(42)
        srsd_flows = []
        for i in range(20):
            flow = srsd_router.route("n_0_0", "n_3_3", f"srsd_{i}")
            if flow:
                srsd_flows.append(flow)

        return baseline_flows, srsd_flows

    def test_correlation_metrics(self, flows_baseline_srsd):
        """Test correlation attack metrics."""
        baseline_flows, srsd_flows = flows_baseline_srsd
        graph = NetworkGraph.create_mesh(rows=4, cols=4)

        metrics = AdversaryCapabilityMetrics(graph)

        corr_baseline = metrics.calculate_correlation_metrics(baseline_flows)
        corr_srsd = metrics.calculate_correlation_metrics(srsd_flows)

        assert corr_baseline.total_flows == len(baseline_flows)
        assert corr_srsd.total_flows == len(srsd_flows)

    def test_fingerprinting_metrics(self, flows_baseline_srsd):
        """Test fingerprinting attack metrics."""
        baseline_flows, srsd_flows = flows_baseline_srsd
        graph = NetworkGraph.create_mesh(rows=4, cols=4)

        metrics = AdversaryCapabilityMetrics(graph)

        fp_baseline = metrics.calculate_fingerprinting_metrics(baseline_flows)
        fp_srsd = metrics.calculate_fingerprinting_metrics(srsd_flows)

        # Baseline should have fewer unique fingerprints (more identifiable)
        assert fp_baseline.unique_fingerprints <= fp_srsd.unique_fingerprints

    def test_path_predictability(self, flows_baseline_srsd):
        """Test path predictability calculation."""
        baseline_flows, srsd_flows = flows_baseline_srsd
        graph = NetworkGraph.create_mesh(rows=4, cols=4)

        metrics = AdversaryCapabilityMetrics(graph)

        pred_baseline = metrics.calculate_path_predictability(baseline_flows)
        pred_srsd = metrics.calculate_path_predictability(srsd_flows)

        # Baseline should have lower entropy (more predictable)
        assert pred_baseline['entropy'] <= pred_srsd['entropy']


class TestEntropyMetrics:
    """Tests for entropy calculations."""

    def test_path_entropy(self):
        """Test path entropy calculation."""
        from src.routing.baseline import RoutingStatistics

        stats = RoutingStatistics()

        # Simulate usage of 3 paths with different frequencies
        stats.path_usage = {
            "A->B->C": 50,  # 50%
            "A->D->C": 30,  # 30%
            "A->E->C": 20,  # 20%
        }

        entropy = calculate_path_entropy(stats)
        assert entropy > 0
        assert entropy < 2  # Max for 3 items is log2(3) ≈ 1.58

    def test_normalized_entropy(self):
        """Test normalized entropy calculation."""
        from src.routing.baseline import RoutingStatistics

        # Uniform distribution = max entropy
        uniform_stats = RoutingStatistics()
        uniform_stats.path_usage = {
            "path1": 10,
            "path2": 10,
            "path3": 10,
            "path4": 10,
        }

        uniform_entropy = calculate_normalized_entropy(uniform_stats)
        assert 0.9 <= uniform_entropy <= 1.0

        # Concentrated distribution = low entropy
        concentrated_stats = RoutingStatistics()
        concentrated_stats.path_usage = {
            "path1": 100,
            "path2": 1,
            "path3": 1,
        }

        concentrated_entropy = calculate_normalized_entropy(concentrated_stats)
        assert concentrated_entropy < uniform_entropy

    def test_recurrence_rate(self):
        """Test recurrence rate calculation."""
        from src.routing.baseline import RoutingStatistics

        stats = RoutingStatistics()
        stats.path_usage = {
            "path1": 90,  # Dominant
            "path2": 5,
            "path3": 5,
        }
        stats.successful_routes = 100  # Required for recurrence calculation

        rate = calculate_recurrence_rate(stats)
        assert rate == 0.9  # 90 out of 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
