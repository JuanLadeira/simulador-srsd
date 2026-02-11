# Plano de Implementação do Frontend com Streamlit

## 1. Objetivo

Criar um dashboard web interativo para o projeto SRSD Simulator utilizando a biblioteca Streamlit. O frontend deve permitir ao usuário configurar, executar e visualizar os resultados das simulações de forma intuitiva e gráfica, facilitando a análise e a demonstração do projeto.

## 2. Estrutura de Arquivos Proposta

```
simulador/
├── app.py                   # Ponto de entrada principal do Streamlit
├── config/
│   └── scenarios.yaml
├── data/
├── docs/
│   └── FRONTEND_PLAN.md     # Este arquivo
├── frontend/                # Novo diretório para código específico do UI
│   ├── __init__.py
│   ├── simulation.py        # Funções para conectar e executar o simulador
│   └── ui_components.py     # Funções para gerar visualizações (gráficos, tabelas)
├── src/
├── tests/
└── requirements.txt         # Atualizado com as novas dependências
```

## 3. Dependências

As seguintes bibliotecas serão adicionadas ao `requirements.txt`:
- `streamlit`
- `pandas`
- `pyvis` (para visualização de grafos interativos)

## 4. Fases de Implementação (Detalhado)

### Fase 1: Estrutura Base e Controles (Concluído)
-   **Status:** [x] Concluído
-   **Descrição:** A estrutura inicial da aplicação foi criada em `app.py`. A interface já possui uma barra lateral que carrega dinamicamente os cenários do arquivo `config/scenarios.yaml` usando `st.selectbox`. Um botão de execução e abas para os resultados também estão presentes.

### Fase 2: Integração com o Simulador
-   **Status:** [ ] A Fazer
-   **Objetivo:** Conectar a interface do Streamlit com o motor de simulação do projeto.

-   **Tarefas Detalhadas:**
    -   **2.1: Criar o Wrapper de Simulação:**
        -   No arquivo `frontend/simulation.py`, criar uma classe `SimulationWrapper`.
        -   O `__init__` desta classe receberá o nome do cenário e um dicionário opcional com parâmetros para override.
        -   Um método `run()` carregará a configuração do cenário do YAML, aplicará os overrides, instanciará o `SimulationRunner` e executará a simulação, retornando o dicionário de resultados.

    -   **2.2: Implementar Lógica de Execução e Cache:**
        -   Em `app.py`, a lógica do `if run_button:` será expandida.
        -   A função `run_simulation_cached(scenario_name, override_params)` será criada em `frontend/simulation.py` e anotada com `@st.cache_data`. Esta função irá instanciar e executar o `SimulationWrapper`.
        -   O `override_params` será um tuplo de itens do dicionário para que seja "hasheável" pelo cache do Streamlit.
        -   `app.py` chamará esta função "cacheada" e passará os parâmetros da UI.

    -   **2.3: Adicionar Feedback de Carregamento:**
        -   Envolver a chamada da simulação em um `with st.spinner("Executando simulação... Isso pode levar alguns instantes."):`.

### Fase 3: Visualização dos Resultados
-   **Status:** [ ] A Fazer
-   **Objetivo:** Exibir os dados gerados pela simulação de forma clara e informativa.

-   **Tarefas Detalhadas:**
    -   **3.1: Aba "Resumo Comparativo":**
        -   Em `frontend/ui_components.py`, criar a função `render_summary(results: dict)`.
        -   Usar `st.columns` para criar um layout com 3 colunas.
        -   Em cada coluna, usar `st.metric` para exibir os KPIs principais do dicionário `results['comparison']`, como:
            - `st.metric("Melhora de Entropia", f"{results['comparison']['entropy_improvement_pct']:.2f}%")`
            - `st.metric("Overhead de Latência", f"{results['comparison']['latency_overhead_pct']:.2f}%")`

    -   **3.2: Aba "Métricas Detalhadas":**
        -   Criar a função `render_detailed_metrics(results: dict)`.
        -   Iterar sobre as chaves dos resultados (`baseline`, `srsd`, `distributed`).
        -   Para cada algoritmo, usar `st.subheader()` e `st.dataframe()` para mostrar as métricas em uma tabela.
        -   Adicionar `st.expander("Ver JSON Completo")` para mostrar o dicionário de resultados brutos com `st.json(results)`.

    -   **3.3: Aba "Visualização da Rede":**
        -   Criar a função `render_network_graph(scenario_config: dict, hiatus_nodes: list)`.
        -   Esta função irá:
            1.  Usar `networkx` para gerar o grafo a partir da configuração da topologia (reaproveitando a lógica de `src.core.graph`).
            2.  Criar um objeto `pyvis.network.Network`, configurando-o para ser interativo.
            3.  Iterar sobre os nós do grafo `networkx`, adicionando-os ao grafo `pyvis`.
            4.  Definir a cor de cada nó: `color='#FF4B4B'` se for um `Hiatus`, `color='#0068C9'` caso contrário.
            5.  Salvar o grafo `pyvis` em um arquivo HTML temporário.
            6.  Ler o conteúdo do HTML e exibi-lo em `app.py` usando `st.components.v1.html(html_content, height=600)`.

### Fase 4: Interatividade Avançada
-   **Status:** [ ] A Fazer
-   **Objetivo:** Permitir que o usuário experimente com os parâmetros da simulação diretamente pela interface.

-   **Tarefas Detalhadas:**
    -   **4.1: Implementar Controles de Override:**
        -   Na barra lateral de `app.py`, adicionar widgets para os parâmetros mais importantes:
            - `num_flows = st.slider("Número de Fluxos", 100, 5000, scenario_config['traffic']['num_flows'])`
            - `num_hiatus = st.number_input("Número de Hiatus", 0, 20, scenario_config['topology'].get('num_hiatus', 3))`
        -   Coletar os valores desses widgets em um `override_params` dict.
        -   Passar este dicionário para a função de simulação "cacheada".

    -   **4.2: Comparador de Resultados Salvos:**
        -   Adicionar uma nova seção no dashboard (talvez uma nova página).
        -   Usar `glob` para listar todos os arquivos `.json` em `data/results/`.
        -   Apresentar a lista em um `st.multiselect`.
        -   Para cada arquivo selecionado, carregar o JSON, extrair as métricas chave e adicionar a um DataFrame do Pandas.
        -   Usar `st.bar_chart` ou `st.line_chart` para plotar a comparação das métricas entre as diferentes execuções.

## 5. Como Executar

Para iniciar o dashboard, execute o seguinte comando no terminal:

```bash
streamlit run app.py
```
