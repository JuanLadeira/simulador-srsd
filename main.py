#!/usr/bin/env python3
"""
SRSD Simulator - Main Entry Point

Validates SRSD (Sistema de Roteamento Seguro Distribuído) hypotheses:
- H1: Structural routing predictability is an exploitable vulnerability
- H2: SRSD with QKD reduces vulnerability without significant performance loss

Usage:
    python main.py                    # Run default scenarios
    python main.py --scenario small_mesh  # Run specific scenario
    python main.py --list             # List available scenarios
    python main.py --validate         # Run validation only
"""

import argparse
import sys
from pathlib import Path

import yaml

from src.simulation import (
    Scenario,
    SimulationRunner,
    BatchRunner,
    create_default_scenarios,
)
from src.analysis import (
    ResultComparator,
    HypothesisValidator,
    ValidationCriteria,
)


def load_scenarios_from_config(config_path: str = "config/scenarios.yaml") -> dict:
    """Load scenarios from YAML configuration file."""
    path = Path(config_path)
    if not path.exists():
        return {}

    with open(path, 'r') as f:
        config = yaml.safe_load(f)

    scenarios = {}
    for name, data in config.items():
        try:
            scenario = Scenario.from_dict(data)
            scenarios[name] = scenario
        except Exception as e:
            print(f"Warning: Failed to load scenario '{name}': {e}")

    return scenarios


def list_scenarios():
    """List all available scenarios."""
    print("\nAvailable Scenarios:")
    print("-" * 50)

    # Built-in scenarios
    print("\nBuilt-in scenarios:")
    for scenario in create_default_scenarios():
        print(f"  - {scenario.name}: {scenario.description}")

    # Config file scenarios
    config_scenarios = load_scenarios_from_config()
    if config_scenarios:
        print("\nConfig file scenarios (config/scenarios.yaml):")
        for name, scenario in config_scenarios.items():
            print(f"  - {name}: {scenario.description}")

    print()


def run_scenario(scenario_name: str, verbose: bool = True) -> dict:
    """Run a single scenario."""
    # Try to find scenario
    scenario = None

    # Check built-in scenarios
    for s in create_default_scenarios():
        if s.name == scenario_name:
            scenario = s
            break

    # Check config file scenarios
    if scenario is None:
        config_scenarios = load_scenarios_from_config()
        if scenario_name in config_scenarios:
            scenario = config_scenarios[scenario_name]

    if scenario is None:
        print(f"Error: Scenario '{scenario_name}' not found")
        sys.exit(1)

    if verbose:
        print(f"\nRunning scenario: {scenario.name}")
        print(f"Description: {scenario.description}")
        print(f"Topology: {scenario.topology.type.value} ({scenario.topology.num_nodes} nodes)")
        print(f"Traffic: {scenario.traffic.pattern.value} ({scenario.traffic.num_flows} flows)")
        print()

    # Run simulation
    runner = SimulationRunner(scenario)
    result = runner.run()

    # Save results
    filepath = runner.save_results(result)

    if verbose:
        print(f"\nResults saved to: {filepath}")
        print(f"Duration: {result.duration:.2f}s")

        # Print summary
        print("\nSummary:")
        for algo_name, algo_result in result.results.items():
            print(f"\n  {algo_name}:")
            print(f"    Successful flows: {algo_result.successful_flows}")
            print(f"    Average latency: {algo_result.avg_latency:.2f}ms")
            print(f"    Path entropy: {algo_result.path_entropy:.4f} bits")
            print(f"    Unique paths: {algo_result.unique_paths}")

        # Print comparison if available
        if result.comparison:
            print("\nComparison (Baseline vs SRSD):")
            if 'baseline_vs_srsd' in result.comparison:
                comp = result.comparison['baseline_vs_srsd']
                print(f"  Entropy improvement: {comp.get('entropy_improvement_pct', 0):.2f}%")
                print(f"  Diversity improvement: {comp.get('diversity_improvement_pct', 0):.2f}%")
                print(f"  Latency overhead: {comp.get('latency_overhead_pct', 0):.2f}%")

    return result.to_dict()


def run_all_scenarios(verbose: bool = True):
    """Run all available scenarios."""
    scenarios = []

    # Built-in scenarios
    scenarios.extend(create_default_scenarios())

    # Config file scenarios
    config_scenarios = load_scenarios_from_config()
    scenarios.extend(config_scenarios.values())

    if not scenarios:
        print("No scenarios available to run")
        return

    print(f"\nRunning {len(scenarios)} scenarios...")
    print("=" * 50)

    batch_runner = BatchRunner(scenarios)
    results = batch_runner.run_all()

    # Print summary
    summary = batch_runner.get_summary()
    print("\n" + "=" * 50)
    print("BATCH RUN SUMMARY")
    print("=" * 50)
    print(f"Total scenarios: {summary['scenarios']}")
    print(f"Total duration: {summary['total_duration']:.2f}s")

    return results


def run_validation(result_dir: str = "data/results", verbose: bool = True):
    """Run hypothesis validation on existing results."""
    path = Path(result_dir)
    if not path.exists():
        print(f"Error: Results directory '{result_dir}' not found")
        print("Run some experiments first with: python main.py")
        sys.exit(1)

    # Find result files
    result_files = list(path.glob("*.json"))
    if not result_files:
        print(f"No result files found in {result_dir}")
        sys.exit(1)

    if verbose:
        print(f"\nLoading {len(result_files)} result files...")

    # Create validator
    validator = HypothesisValidator(ValidationCriteria())

    for filepath in result_files:
        name = filepath.stem
        try:
            validator.load_result(name, str(filepath))
            if verbose:
                print(f"  Loaded: {name}")
        except Exception as e:
            print(f"  Warning: Failed to load {name}: {e}")

    # Run validation
    if verbose:
        print("\nRunning hypothesis validation...")

    report = validator.generate_validation_report()
    print("\n" + report)

    # Save validation results
    validation_result = validator.validate_all()
    validation_path = path / "validation_results.json"
    validation_result.save(str(validation_path))

    if verbose:
        print(f"\nValidation results saved to: {validation_path}")

    return validation_result


def run_quick_demo():
    """Run a quick demonstration with minimal configuration."""
    print("\n" + "=" * 50)
    print("SRSD SIMULATOR - QUICK DEMO")
    print("=" * 50)

    # Create a small scenario
    from src.simulation import (
        TopologyConfig,
        TrafficConfig,
        ExperimentConfig,
        TopologyType,
        TrafficPattern,
    )

    scenario = Scenario(
        name="quick_demo",
        description="Quick demonstration of SRSD simulator",
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
            name="demo",
            duration=10.0,
            warmup=1.0,
            test_baseline=True,
            test_srsd=True,
        ),
    )

    print(f"\nTopology: 3x3 mesh network (9 nodes)")
    print(f"Traffic: 100 uniform random flows")
    print(f"Comparing: Baseline vs SRSD routing\n")

    # Run
    runner = SimulationRunner(scenario)
    result = runner.run()

    # Display results
    print("\nRESULTS:")
    print("-" * 40)

    baseline = result.results.get('baseline')
    srsd = result.results.get('srsd')

    if baseline and srsd:
        print(f"\n{'Metric':<25} {'Baseline':>12} {'SRSD':>12} {'Change':>12}")
        print("-" * 61)

        # Path entropy
        entropy_change = srsd.path_entropy - baseline.path_entropy
        print(f"{'Path Entropy (bits)':<25} {baseline.path_entropy:>12.4f} {srsd.path_entropy:>12.4f} {entropy_change:>+12.4f}")

        # Unique paths
        paths_change = srsd.unique_paths - baseline.unique_paths
        print(f"{'Unique Paths':<25} {baseline.unique_paths:>12} {srsd.unique_paths:>12} {paths_change:>+12}")

        # Latency
        latency_change = srsd.avg_latency - baseline.avg_latency
        print(f"{'Avg Latency (ms)':<25} {baseline.avg_latency:>12.2f} {srsd.avg_latency:>12.2f} {latency_change:>+12.2f}")

        # Success rate
        baseline_success = baseline.successful_flows / (baseline.successful_flows + baseline.failed_flows) * 100
        srsd_success = srsd.successful_flows / (srsd.successful_flows + srsd.failed_flows) * 100
        print(f"{'Success Rate (%)':<25} {baseline_success:>12.1f} {srsd_success:>12.1f}")

        print("\n" + "-" * 40)
        print("\nINTERPRETATION:")

        if entropy_change > 0:
            print(f"  + SRSD increased path entropy by {entropy_change:.4f} bits")
            print(f"    -> Routing is LESS predictable to adversaries")
        else:
            print(f"  - SRSD did not improve entropy in this scenario")

        if paths_change > 0:
            print(f"  + SRSD used {paths_change} more unique paths")
            print(f"    -> Greater path diversity achieved")

        overhead_pct = (latency_change / baseline.avg_latency * 100) if baseline.avg_latency > 0 else 0
        if overhead_pct < 20:
            print(f"  + Latency overhead ({overhead_pct:.1f}%) is within acceptable limits")
        else:
            print(f"  - Latency overhead ({overhead_pct:.1f}%) may be significant")

    print("\n" + "=" * 50)
    print("Demo complete! Run 'python main.py --help' for more options.")
    print("=" * 50 + "\n")

    return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SRSD Network Routing Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     Run quick demo
  python main.py --scenario small_mesh   Run specific scenario
  python main.py --all               Run all available scenarios
  python main.py --validate          Validate hypotheses from results
  python main.py --list              List available scenarios
        """,
    )

    parser.add_argument(
        "--scenario", "-s",
        type=str,
        help="Run specific scenario by name",
    )

    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run all available scenarios",
    )

    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available scenarios",
    )

    parser.add_argument(
        "--validate", "-v",
        action="store_true",
        help="Run hypothesis validation on existing results",
    )

    parser.add_argument(
        "--demo", "-d",
        action="store_true",
        help="Run quick demonstration",
    )

    parser.add_argument(
        "--results-dir", "-r",
        type=str,
        default="data/results",
        help="Directory for results (default: data/results)",
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Reduce output verbosity",
    )

    args = parser.parse_args()

    verbose = not args.quiet

    # Handle commands
    if args.list:
        list_scenarios()
    elif args.validate:
        run_validation(args.results_dir, verbose)
    elif args.all:
        run_all_scenarios(verbose)
    elif args.scenario:
        run_scenario(args.scenario, verbose)
    elif args.demo:
        run_quick_demo()
    else:
        # Default: run quick demo
        run_quick_demo()


if __name__ == "__main__":
    main()
