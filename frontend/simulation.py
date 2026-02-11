"""
Simulation wrapper for Streamlit frontend.

Provides cached simulation execution and scenario loading.
"""

import streamlit as st
import yaml
from pathlib import Path

from src.simulation.runner import SimulationRunner
from src.simulation.scenario import Scenario


@st.cache_data(show_spinner=False)
def run_simulation_cached(scenario_name: str, override_params: tuple) -> dict:
    """
    Execute simulation with Streamlit caching.

    Args:
        scenario_name: Name of the scenario to run
        override_params: Tuple of (key, value) pairs to override scenario params

    Returns:
        Dictionary with simulation results
    """
    scenario = load_scenario(scenario_name)

    # Apply overrides
    overrides = dict(override_params)
    if "num_flows" in overrides:
        scenario.traffic.num_flows = overrides["num_flows"]
    if "num_hiatus" in overrides:
        scenario.experiment.num_hiatus = overrides["num_hiatus"]

    runner = SimulationRunner(scenario)
    result = runner.run()
    return result.to_dict()


def load_scenario(scenario_name: str) -> Scenario:
    """
    Load scenario from YAML configuration.

    Args:
        scenario_name: Name of the scenario in the YAML file

    Returns:
        Scenario object configured from YAML
    """
    config_path = Path("config/scenarios.yaml")
    with open(config_path, "r") as f:
        scenarios = yaml.safe_load(f)

    config = scenarios[scenario_name]
    return Scenario.from_dict(config)


def get_scenario_config(scenario_name: str) -> dict:
    """
    Get raw scenario configuration from YAML.

    Args:
        scenario_name: Name of the scenario

    Returns:
        Raw dictionary configuration
    """
    config_path = Path("config/scenarios.yaml")
    with open(config_path, "r") as f:
        scenarios = yaml.safe_load(f)

    return scenarios.get(scenario_name, {})
