"""
SRSD Network Routing Simulator Dashboard.

Web interface for running and visualizing SRSD simulations.
"""

import streamlit as st
import yaml
from pathlib import Path

from frontend.simulation import run_simulation_cached
from frontend.ui_components import (
    render_summary,
    render_detailed_metrics,
    render_network_graph,
    render_adversary_analysis,
    render_history,
    render_comparison,
    render_history_sidebar,
)
from frontend.history import (
    save_result,
    load_result,
    list_history,
    delete_result,
)

# Page configuration
st.set_page_config(
    page_title="SRSD Simulator Dashboard",
    page_icon="icon.svg",
    layout="wide",
)

st.title("SRSD Network Routing Simulator")


# Cache for loading scenarios
@st.cache_data
def load_scenarios():
    """Load all scenarios from YAML configuration."""
    config_path = Path("config/scenarios.yaml")
    if not config_path.exists():
        st.error("Arquivo de configuracao `config/scenarios.yaml` nao encontrado!")
        return {}
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


scenarios = load_scenarios()

# Session state initialization
if "results" not in st.session_state:
    st.session_state.results = None
if "last_scenario" not in st.session_state:
    st.session_state.last_scenario = None
if "comparison_results" not in st.session_state:
    st.session_state.comparison_results = []

# Sidebar controls
with st.sidebar:
    st.header("Configuracao")

    scenario_name = st.selectbox(
        "Cenario",
        options=list(scenarios.keys()),
        format_func=lambda x: scenarios[x].get("description", x)[:50],
    )

    scenario_config = scenarios.get(scenario_name, {})
    st.caption(scenario_config.get("description", ""))

    # Override parameters
    st.subheader("Parametros")

    traffic_config = scenario_config.get("traffic", {})
    num_flows = st.slider(
        "Numero de Fluxos",
        min_value=100,
        max_value=5000,
        value=traffic_config.get("num_flows", 500),
        step=100,
    )

    experiment_config = scenario_config.get("experiment", {})
    num_hiatus = st.number_input(
        "Numero de Hiatus",
        min_value=1,
        max_value=20,
        value=experiment_config.get("num_hiatus", 3),
    )

    # Auto-save option
    auto_save = st.checkbox("Salvar no historico", value=True)

    run_button = st.button(
        "Executar Simulacao", type="primary", use_container_width=True
    )

    # History comparison section
    st.divider()
    history = list_history()
    selected_files = render_history_sidebar(history)

    if selected_files and st.button("Comparar Selecionados"):
        comparison_list = []
        for filename in selected_files:
            data = load_result(filename)
            if data:
                name = data.get("metadata", {}).get("scenario_name", filename)
                comparison_list.append((name, data.get("results", {})))
        st.session_state.comparison_results = comparison_list

# Execute simulation
if run_button:
    override_params = tuple(
        [
            ("num_flows", num_flows),
            ("num_hiatus", num_hiatus),
        ]
    )

    with st.spinner("Executando simulacao... Isso pode levar alguns instantes."):
        try:
            results = run_simulation_cached(scenario_name, override_params)
            st.session_state.results = results
            st.session_state.last_scenario = scenario_name

            # Auto-save to history
            if auto_save:
                filepath = save_result(results, scenario_name)
                st.success(f"Simulacao concluida e salva!")
            else:
                st.success("Simulacao concluida!")
        except Exception as e:
            st.error(f"Erro na simulacao: {e}")

# Result tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "Resumo Comparativo",
        "Metricas Detalhadas",
        "Visualizacao da Rede",
        "Analise do Adversario",
        "Historico",
        "Comparador",
    ]
)

with tab1:
    render_summary(st.session_state.results)

with tab2:
    render_detailed_metrics(st.session_state.results)

with tab3:
    render_network_graph(scenario_config)

with tab4:
    render_adversary_analysis(st.session_state.results)

with tab5:
    # History tab
    history = list_history()

    def handle_load(filename):
        data = load_result(filename)
        if data:
            st.session_state.results = data.get("results", {})
            st.session_state.last_scenario = data.get("metadata", {}).get(
                "scenario_name", ""
            )
            st.rerun()

    def handle_delete(filename):
        delete_result(filename)
        st.rerun()

    render_history(history, handle_load, handle_delete)

with tab6:
    # Comparison tab
    if st.session_state.comparison_results:
        render_comparison(st.session_state.comparison_results)
    else:
        st.info(
            "Selecione simulacoes na barra lateral e clique em 'Comparar Selecionados'."
        )

        # Quick compare with current result
        if st.session_state.results and history:
            st.subheader("Comparacao Rapida")
            st.write("Compare o resultado atual com uma simulacao do historico:")

            selected_for_quick = st.selectbox(
                "Selecionar do historico",
                options=[h.get("filename") for h in history],
                format_func=lambda x: f"{x[:30]}..." if len(x) > 30 else x,
            )

            if st.button("Comparar com Atual"):
                data = load_result(selected_for_quick)
                if data:
                    current_name = st.session_state.last_scenario or "Atual"
                    hist_name = data.get("metadata", {}).get("scenario_name", "Historico")
                    st.session_state.comparison_results = [
                        (current_name, st.session_state.results),
                        (hist_name, data.get("results", {})),
                    ]
                    st.rerun()
