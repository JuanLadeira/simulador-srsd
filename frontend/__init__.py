"""
Frontend module for SRSD Simulator Dashboard.

Provides Streamlit-based web interface components for:
- Running simulations
- Visualizing results
- Network graph rendering
- History management
- Result comparison
"""

from .simulation import run_simulation_cached, load_scenario
from .ui_components import (
    render_summary,
    render_detailed_metrics,
    render_network_graph,
    render_adversary_analysis,
    render_history,
    render_comparison,
    render_history_sidebar,
)
from .history import (
    save_result,
    load_result,
    list_history,
    delete_result,
    clear_history,
)

__all__ = [
    "run_simulation_cached",
    "load_scenario",
    "render_summary",
    "render_detailed_metrics",
    "render_network_graph",
    "render_adversary_analysis",
    "render_history",
    "render_comparison",
    "render_history_sidebar",
    "save_result",
    "load_result",
    "list_history",
    "delete_result",
    "clear_history",
]
