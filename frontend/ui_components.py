"""
UI Components for SRSD Simulator Dashboard.

Provides visualization and rendering functions for Streamlit interface.
"""

import streamlit as st
import pandas as pd


def render_summary(results: dict) -> None:
    """
    Render comparative summary tab with key metrics.

    Args:
        results: Dictionary with simulation results
    """
    if not results:
        st.info("Execute uma simulacao para ver os resultados.")
        return

    comparison = results.get("comparison", {}).get("baseline_vs_srsd", {})

    col1, col2, col3 = st.columns(3)

    with col1:
        entropy_imp = comparison.get("entropy_improvement_pct", 0)
        st.metric(
            "Melhora de Entropia",
            f"{entropy_imp:.1f}%",
            delta=f"{entropy_imp:.1f}%" if entropy_imp > 0 else None,
        )

    with col2:
        latency_oh = comparison.get("latency_overhead_pct", 0)
        st.metric(
            "Overhead de Latencia",
            f"{latency_oh:.1f}%",
            delta=f"{latency_oh:.1f}%",
            delta_color="inverse",
        )

    with col3:
        diversity = comparison.get("diversity_improvement_pct", 0)
        st.metric(
            "Melhora de Diversidade",
            f"{diversity:.1f}%",
            delta=f"{diversity:.1f}%" if diversity > 0 else None,
        )

    # Additional comparison details
    st.subheader("Detalhes da Comparacao")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**Baseline**")
        baseline_entropy = comparison.get("baseline_entropy", 0)
        baseline_paths = comparison.get("baseline_unique_paths", 0)
        st.write(f"- Entropia: {baseline_entropy:.4f} bits")
        st.write(f"- Caminhos unicos: {baseline_paths}")

    with col_right:
        st.markdown("**SRSD**")
        srsd_entropy = comparison.get("srsd_entropy", 0)
        srsd_paths = comparison.get("srsd_unique_paths", 0)
        st.write(f"- Entropia: {srsd_entropy:.4f} bits")
        st.write(f"- Caminhos unicos: {srsd_paths}")


def render_detailed_metrics(results: dict) -> None:
    """
    Render detailed metrics tab with per-algorithm tables.

    Args:
        results: Dictionary with simulation results
    """
    if not results:
        st.info("Execute uma simulacao para ver os resultados.")
        return

    algo_results = results.get("results", {})

    for algo_name, algo_data in algo_results.items():
        with st.expander(f"Algoritmo: {algo_name.upper()}", expanded=True):
            metrics_df = pd.DataFrame(
                {
                    "Metrica": [
                        "Fluxos Sucesso",
                        "Fluxos Falha",
                        "Latencia Media",
                        "Hops Medios",
                        "Entropia",
                        "Caminhos Unicos",
                    ],
                    "Valor": [
                        algo_data.get("successful_flows", 0),
                        algo_data.get("failed_flows", 0),
                        f"{algo_data.get('avg_latency', 0):.2f} ms",
                        f"{algo_data.get('avg_hops', 0):.2f}",
                        f"{algo_data.get('path_entropy', 0):.4f} bits",
                        algo_data.get("unique_paths", 0),
                    ],
                }
            )
            st.dataframe(metrics_df, use_container_width=True, hide_index=True)

    # Raw JSON data
    with st.expander("JSON Completo"):
        st.json(results)


def render_network_graph(scenario_config: dict, hiatus_nodes: list = None) -> None:
    """
    Render interactive network visualization using pyvis.

    Args:
        scenario_config: Scenario configuration dictionary
        hiatus_nodes: List of hiatus node IDs to highlight
    """
    try:
        from pyvis.network import Network
    except ImportError:
        st.warning(
            "pyvis nao esta instalado. Execute: pip install pyvis"
        )
        return

    from src.core.graph import NetworkGraph

    # Create graph based on topology config
    topo_config = scenario_config.get("topology", {})
    topo_type = topo_config.get("type", "mesh")

    try:
        if topo_type == "mesh":
            graph = NetworkGraph.create_mesh(
                rows=topo_config.get("rows", 4),
                cols=topo_config.get("cols", 4),
            )
        elif topo_type == "barabasi_albert":
            graph = NetworkGraph.create_barabasi_albert(
                n=topo_config.get("num_nodes", 20),
                m=topo_config.get("ba_m", 2),
                seed=topo_config.get("seed"),
            )
        elif topo_type == "watts_strogatz":
            graph = NetworkGraph.create_watts_strogatz(
                n=topo_config.get("num_nodes", 20),
                k=topo_config.get("ws_k", 4),
                p=topo_config.get("ws_p", 0.1),
                seed=topo_config.get("seed"),
            )
        else:
            st.warning(f"Tipo de topologia nao suportado: {topo_type}")
            return
    except Exception as e:
        st.error(f"Erro ao criar grafo: {e}")
        return

    hiatus_set = set(hiatus_nodes or [])

    # Create pyvis network with notebook=True to avoid file copying issues
    net = Network(
        height="500px",
        width="100%",
        bgcolor="#0E1117",
        font_color="white",
        notebook=True,
    )
    net.barnes_hut()

    # Add nodes
    for node in graph.get_nodes():
        color = "#FF4B4B" if node.id in hiatus_set else "#0068C9"
        net.add_node(node.id, label=node.id, color=color, size=20)

    # Add edges
    for edge in graph.get_edges():
        net.add_edge(edge.source, edge.target)

    # Generate HTML content directly
    html_content = net.generate_html()

    st.components.v1.html(html_content, height=520)

    # Show graph statistics
    st.caption(
        f"Topologia: {topo_type} | Nos: {graph.num_nodes} | Arestas: {graph.num_edges}"
    )


def render_adversary_analysis(results: dict) -> None:
    """
    Render adversary analysis tab with security metrics.

    Args:
        results: Dictionary with simulation results
    """
    if not results:
        st.info("Execute uma simulacao para ver os resultados.")
        return

    comparison = results.get("comparison", {}).get("adversary", {})
    algo_results = results.get("results", {})

    st.subheader("Capacidade do Adversario por Algoritmo")

    data = []
    for algo_name, algo_data in algo_results.items():
        data.append(
            {
                "Algoritmo": algo_name.upper(),
                "Correlacao": f"{algo_data.get('adversary_correlation', 0)*100:.1f}%",
                "Identificacao": f"{algo_data.get('adversary_identification', 0)*100:.1f}%",
            }
        )

    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.caption(
            """
        **Correlacao**: Taxa de sucesso do adversario em correlacionar entrada/saida.
        **Identificacao**: Taxa de sucesso em identificar origem/destino.
        Valores menores = melhor seguranca.
        """
        )

    # Adversary comparison if available
    if comparison:
        st.subheader("Comparacao de Seguranca")

        col1, col2 = st.columns(2)

        with col1:
            baseline_corr = comparison.get("baseline_correlation", 0)
            st.metric(
                "Correlacao Baseline",
                f"{baseline_corr*100:.1f}%",
            )

        with col2:
            srsd_corr = comparison.get("srsd_correlation", 0)
            improvement = (baseline_corr - srsd_corr) * 100 if baseline_corr > 0 else 0
            st.metric(
                "Correlacao SRSD",
                f"{srsd_corr*100:.1f}%",
                delta=f"-{improvement:.1f}%" if improvement > 0 else None,
            )


def render_history(history: list, on_load: callable, on_delete: callable) -> None:
    """
    Render simulation history list.

    Args:
        history: List of history metadata
        on_load: Callback when loading a result
        on_delete: Callback when deleting a result
    """
    if not history:
        st.info("Nenhuma simulacao salva no historico.")
        return

    st.subheader(f"Historico ({len(history)} simulacoes)")

    for i, item in enumerate(history):
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

            with col1:
                scenario = item.get("scenario_name", "N/A")
                timestamp = item.get("timestamp", "")[:19].replace("T", " ")
                st.markdown(f"**{scenario}**")
                st.caption(timestamp)

            with col2:
                entropy = item.get("entropy_improvement", 0)
                st.metric("Entropia", f"{entropy:+.1f}%", label_visibility="collapsed")

            with col3:
                latency = item.get("latency_overhead", 0)
                st.metric("Latencia", f"{latency:+.1f}%", label_visibility="collapsed")

            with col4:
                if st.button("Carregar", key=f"load_{i}"):
                    on_load(item.get("filename"))
                if st.button("Excluir", key=f"del_{i}"):
                    on_delete(item.get("filename"))

            st.divider()


def render_comparison(results_list: list[tuple[str, dict]]) -> None:
    """
    Render comparison between multiple simulation results.

    Args:
        results_list: List of (name, results) tuples to compare
    """
    if len(results_list) < 2:
        st.info("Selecione pelo menos 2 simulacoes para comparar.")
        return

    st.subheader("Comparacao de Simulacoes")

    # Build comparison dataframe
    data = []
    for name, results in results_list:
        comparison = results.get("comparison", {}).get("baseline_vs_srsd", {})
        algo_results = results.get("results", {})

        srsd_data = algo_results.get("srsd", {})
        baseline_data = algo_results.get("baseline", {})

        data.append(
            {
                "Simulacao": name,
                "Entropia SRSD": f"{srsd_data.get('path_entropy', 0):.4f}",
                "Entropia Baseline": f"{baseline_data.get('path_entropy', 0):.4f}",
                "Melhora Entropia (%)": f"{comparison.get('entropy_improvement_pct', 0):.1f}",
                "Latencia SRSD": f"{srsd_data.get('avg_latency', 0):.2f}",
                "Latencia Baseline": f"{baseline_data.get('avg_latency', 0):.2f}",
                "Overhead (%)": f"{comparison.get('latency_overhead_pct', 0):.1f}",
                "Caminhos SRSD": srsd_data.get("unique_paths", 0),
                "Caminhos Baseline": baseline_data.get("unique_paths", 0),
            }
        )

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Visual comparison charts
    st.subheader("Graficos Comparativos")

    col1, col2 = st.columns(2)

    with col1:
        # Entropy comparison
        entropy_data = pd.DataFrame(
            {
                "Simulacao": [name for name, _ in results_list],
                "SRSD": [
                    r.get("results", {}).get("srsd", {}).get("path_entropy", 0)
                    for _, r in results_list
                ],
                "Baseline": [
                    r.get("results", {}).get("baseline", {}).get("path_entropy", 0)
                    for _, r in results_list
                ],
            }
        )
        st.bar_chart(entropy_data.set_index("Simulacao"))
        st.caption("Entropia de Caminhos (bits)")

    with col2:
        # Latency comparison
        latency_data = pd.DataFrame(
            {
                "Simulacao": [name for name, _ in results_list],
                "SRSD": [
                    r.get("results", {}).get("srsd", {}).get("avg_latency", 0)
                    for _, r in results_list
                ],
                "Baseline": [
                    r.get("results", {}).get("baseline", {}).get("avg_latency", 0)
                    for _, r in results_list
                ],
            }
        )
        st.bar_chart(latency_data.set_index("Simulacao"))
        st.caption("Latencia Media (ms)")


def render_history_sidebar(history: list) -> list[str]:
    """
    Render history selection in sidebar for comparison.

    Args:
        history: List of history metadata

    Returns:
        List of selected filenames
    """
    if not history:
        return []

    st.subheader("Comparar Simulacoes")

    selected = []
    for item in history[:10]:  # Limit to 10 most recent
        scenario = item.get("scenario_name", "N/A")
        timestamp = item.get("timestamp", "")[:16].replace("T", " ")
        label = f"{scenario} ({timestamp})"

        if st.checkbox(label, key=f"cmp_{item.get('filename')}"):
            selected.append(item.get("filename"))

    return selected
