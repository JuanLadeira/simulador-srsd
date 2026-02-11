"""
History management for SRSD Simulator.

Handles saving, loading, and managing simulation results.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

HISTORY_DIR = Path("data/history")


def ensure_history_dir() -> None:
    """Ensure history directory exists."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def save_result(results: dict, scenario_name: str) -> str:
    """
    Save simulation results to history.

    Args:
        results: Simulation results dictionary
        scenario_name: Name of the scenario

    Returns:
        Path to saved file
    """
    ensure_history_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{scenario_name}_{timestamp}.json"
    filepath = HISTORY_DIR / filename

    # Add metadata
    save_data = {
        "metadata": {
            "scenario_name": scenario_name,
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
        },
        "results": results,
    }

    with open(filepath, "w") as f:
        json.dump(save_data, f, indent=2)

    return str(filepath)


def load_result(filename: str) -> Optional[dict]:
    """
    Load simulation result from history.

    Args:
        filename: Name of the file to load

    Returns:
        Loaded results or None if not found
    """
    filepath = HISTORY_DIR / filename
    if not filepath.exists():
        return None

    with open(filepath, "r") as f:
        return json.load(f)


def list_history() -> list[dict]:
    """
    List all saved simulation results.

    Returns:
        List of metadata dictionaries sorted by timestamp (newest first)
    """
    ensure_history_dir()

    history = []
    for filepath in HISTORY_DIR.glob("*.json"):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                metadata = data.get("metadata", {})
                metadata["filename"] = filepath.name
                # Extract key metrics for preview
                results = data.get("results", {})
                comparison = results.get("comparison", {}).get("baseline_vs_srsd", {})
                metadata["entropy_improvement"] = comparison.get(
                    "entropy_improvement_pct", 0
                )
                metadata["latency_overhead"] = comparison.get("latency_overhead_pct", 0)
                history.append(metadata)
        except (json.JSONDecodeError, KeyError):
            continue

    # Sort by timestamp descending
    history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return history


def delete_result(filename: str) -> bool:
    """
    Delete a saved result.

    Args:
        filename: Name of the file to delete

    Returns:
        True if deleted, False if not found
    """
    filepath = HISTORY_DIR / filename
    if filepath.exists():
        filepath.unlink()
        return True
    return False


def clear_history() -> int:
    """
    Clear all history.

    Returns:
        Number of files deleted
    """
    ensure_history_dir()
    count = 0
    for filepath in HISTORY_DIR.glob("*.json"):
        filepath.unlink()
        count += 1
    return count
