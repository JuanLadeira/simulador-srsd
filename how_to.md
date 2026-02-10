# Como Usar o Simulador SRSD

Este guia explica como instalar, configurar, executar e testar o simulador SRSD.

---

## Índice

1. [Instalação](#instalação)
2. [Execução Rápida](#execução-rápida)
3. [Comandos Disponíveis](#comandos-disponíveis)
4. [Cenários de Teste](#cenários-de-teste)
5. [Criando Cenários Personalizados](#criando-cenários-personalizados)
6. [Executando Testes](#executando-testes)
7. [Interpretando Resultados](#interpretando-resultados)
8. [Validação de Hipóteses](#validação-de-hipóteses)
9. [Uso Programático](#uso-programático)
10. [Troubleshooting](#troubleshooting)

---

## Instalação

### Pré-requisitos

- Python 3.11 ou superior
- pip (gerenciador de pacotes Python)

### Passos

```bash
# 1. Clone ou navegue até o diretório do projeto
cd /caminho/para/simulador

# 2. (Opcional) Crie um ambiente virtual
python -m venv venv

# 3. Ative o ambiente virtual
# Linux/Mac:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate

# 4. Instale as dependências
pip install -r requirements.txt
```

### Verificar Instalação

```bash
# Verificar se as dependências estão instaladas
python -c "import networkx, numpy, yaml; print('OK')"

# Verificar se o projeto pode ser importado
python -c "from src.core import NetworkGraph; print('OK')"
```

---

## Execução Rápida

### Demo Básica

O comando mais simples para ver o simulador em ação:

```bash
python main.py
```

Isso executa uma demonstração rápida com:
- Rede mesh 3x3 (9 nós)
- 100 fluxos de tráfego
- Comparação Baseline vs SRSD

### Saída Esperada

```
==================================================
SRSD SIMULATOR - QUICK DEMO
==================================================

Topology: 3x3 mesh network (9 nodes)
Traffic: 100 uniform random flows
Comparing: Baseline vs SRSD routing

RESULTS:
----------------------------------------

Metric                        Baseline         SRSD       Change
-------------------------------------------------------------
Path Entropy (bits)             5.5435       5.9710      +0.4275
Unique Paths                        53           70          +17
Avg Latency (ms)                  2.04         2.18        +0.14
Success Rate (%)                 100.0        100.0

INTERPRETATION:
  + SRSD increased path entropy by 0.4275 bits
    -> Routing is LESS predictable to adversaries
  + SRSD used 17 more unique paths
    -> Greater path diversity achieved
  + Latency overhead (6.9%) is within acceptable limits
```

---

## Comandos Disponíveis

### Listar Cenários

```bash
python main.py --list
# ou
python main.py -l
```

Mostra todos os cenários disponíveis (built-in e do arquivo de configuração).

### Executar Cenário Específico

```bash
python main.py --scenario nome_do_cenario
# ou
python main.py -s nome_do_cenario

# Exemplos:
python main.py -s small_mesh
python main.py -s medium_scalefree
python main.py -s qkd_network
```

### Executar Todos os Cenários

```bash
python main.py --all
# ou
python main.py -a
```

Executa todos os cenários disponíveis em sequência.

### Validar Hipóteses

```bash
python main.py --validate
# ou
python main.py -v
```

Analisa resultados existentes em `data/results/` e valida H1 e H2.

### Modo Silencioso

```bash
python main.py --scenario small_mesh --quiet
# ou
python main.py -s small_mesh -q
```

### Ajuda

```bash
python main.py --help
```

---

## Cenários de Teste

### Cenários Disponíveis

| Cenário | Topologia | Nós | Fluxos | Descrição |
|---------|-----------|-----|--------|-----------|
| `small_mesh` | Mesh 4x4 | 16 | 500 | Teste básico |
| `medium_scalefree` | Barabási-Albert | 50 | 1000 | Rede tipo Internet |
| `small_world` | Watts-Strogatz | 40 | 800 | Rede small-world |
| `qkd_network` | Barabási-Albert | 30 | 600 | Com cobertura QKD |
| `large_scale` | Barabási-Albert | 100 | 5000 | Teste de escala |
| `adversary_test` | Mesh 5x5 | 25 | 1000 | Foco em adversário |
| `burst_traffic` | Watts-Strogatz | 35 | 1200 | Tráfego em rajadas |
| `full_qkd` | Mesh 4x4 | 16 | 400 | QKD 100% cobertura |

### Exemplo de Execução

```bash
# Teste básico rápido
python main.py -s small_mesh

# Teste de escala (demora mais)
python main.py -s large_scale

# Teste com QKD
python main.py -s qkd_network
```

---

## Criando Cenários Personalizados

### Via Arquivo YAML

Edite `config/scenarios.yaml` para adicionar novos cenários:

```yaml
meu_cenario:
  name: meu_cenario
  description: "Meu cenário personalizado"

  topology:
    type: mesh          # mesh, barabasi_albert, watts_strogatz, random
    rows: 5             # para mesh
    cols: 5             # para mesh
    num_nodes: 25       # para outros tipos
    bidirectional: true
    qkd_enabled: false
    qkd_coverage: 0.5   # 0.0 a 1.0
    seed: 42

  traffic:
    pattern: uniform    # uniform, hotspot, burst, sequential, realistic
    num_flows: 1000
    flow_rate: 20.0     # fluxos por segundo
    hotspot_nodes: 3    # para pattern=hotspot
    hotspot_concentration: 0.7
    seed: 42

  experiment:
    name: meu_experimento
    duration: 100.0
    warmup: 10.0
    test_baseline: true
    test_srsd: true
    test_srsd_qkd: false
    srsd_k_paths: 5
    srsd_recurrence_penalty: 2.0
    output_dir: data/results
```

Depois execute:

```bash
python main.py -s meu_cenario
```

### Via Código Python

```python
from src.simulation import (
    Scenario, TopologyConfig, TrafficConfig, ExperimentConfig,
    TopologyType, TrafficPattern, SimulationRunner
)

# Criar cenário
scenario = Scenario(
    name="custom_test",
    description="Teste personalizado",
    topology=TopologyConfig(
        type=TopologyType.BARABASI_ALBERT,
        num_nodes=30,
        ba_m=3,
        seed=42,
    ),
    traffic=TrafficConfig(
        pattern=TrafficPattern.HOTSPOT,
        num_flows=500,
        hotspot_nodes=3,
        seed=42,
    ),
    experiment=ExperimentConfig(
        test_baseline=True,
        test_srsd=True,
    ),
)

# Executar
runner = SimulationRunner(scenario)
result = runner.run()

# Ver resultados
print(f"Baseline entropy: {result.results['baseline'].path_entropy:.4f}")
print(f"SRSD entropy: {result.results['srsd'].path_entropy:.4f}")
```

---

## Executando Testes

### Executar Todos os Testes

```bash
pytest tests/ -v
```

### Executar Testes Específicos

```bash
# Apenas testes do core
pytest tests/test_core.py -v

# Apenas testes de roteamento
pytest tests/test_routing.py -v

# Apenas testes do adversário
pytest tests/test_adversary.py -v

# Apenas testes de simulação
pytest tests/test_simulation.py -v
```

### Executar Teste Específico

```bash
# Teste individual
pytest tests/test_core.py::TestNetworkGraph::test_shortest_path -v

# Testes de uma classe
pytest tests/test_routing.py::TestSRSDRouter -v
```

### Com Cobertura de Código

```bash
# Instalar pytest-cov se necessário
pip install pytest-cov

# Executar com cobertura
pytest tests/ --cov=src --cov-report=html

# Abrir relatório (gera em htmlcov/index.html)
```

### Testes Rápidos vs Completos

```bash
# Rápido (apenas testes unitários simples)
pytest tests/test_core.py tests/test_routing.py -v

# Completo (inclui testes de integração)
pytest tests/ -v
```

### Saída Esperada

```
======================== test session starts ========================
platform linux -- Python 3.11.10, pytest-8.3.5
collected 66 items

tests/test_adversary.py ............                            [ 18%]
tests/test_core.py .....................                        [ 50%]
tests/test_routing.py ............                              [ 68%]
tests/test_simulation.py ....................                   [100%]

======================== 66 passed in 1.28s =========================
```

---

## Interpretando Resultados

### Métricas Principais

| Métrica | Significado | Bom para SRSD |
|---------|-------------|---------------|
| **Path Entropy** | Diversidade de rotas (bits) | Maior é melhor |
| **Unique Paths** | Número de rotas distintas usadas | Maior é melhor |
| **Avg Latency** | Latência média (ms) | Menor overhead é melhor |
| **Success Rate** | Taxa de sucesso de roteamento | Manter alta (>95%) |

### Interpretação da Entropia

- **Entropia baixa (< 1 bit)**: Roteamento muito previsível, vulnerável
- **Entropia média (1-3 bits)**: Alguma diversidade
- **Entropia alta (> 3 bits)**: Boa diversidade, difícil de prever

### Comparação Baseline vs SRSD

```
Entropy Improvement: +0.4275 bits  → SRSD é menos previsível
Diversity Improvement: +17 paths   → SRSD usa mais rotas
Latency Overhead: +6.9%            → Custo aceitável (<20%)
```

### Arquivos de Resultado

Os resultados são salvos em `data/results/`:

```
data/results/
├── small_mesh_20240210_143022.json
├── medium_scalefree_20240210_143145.json
└── validation_results.json
```

Formato do arquivo JSON:

```json
{
  "scenario_name": "small_mesh",
  "timestamp": "2024-02-10T14:30:22",
  "duration": 5.23,
  "results": {
    "baseline": {
      "algorithm": "baseline",
      "successful_flows": 500,
      "avg_latency": 10.5,
      "path_entropy": 1.234,
      "unique_paths": 15
    },
    "srsd": {
      "algorithm": "srsd",
      "successful_flows": 500,
      "avg_latency": 11.2,
      "path_entropy": 2.456,
      "unique_paths": 42
    }
  },
  "comparison": {
    "baseline_vs_srsd": {
      "entropy_improvement_pct": 99.03,
      "latency_overhead_pct": 6.67
    }
  }
}
```

---

## Validação de Hipóteses

### Executar Validação

Após executar alguns cenários:

```bash
# Executar cenários
python main.py -s small_mesh
python main.py -s medium_scalefree

# Validar hipóteses
python main.py --validate
```

### Relatório de Validação

```
======================================================================
SRSD HYPOTHESIS VALIDATION REPORT
======================================================================

OVERALL RESULT
--------------------------------------------------
Status: VALIDATED
Summary: Both hypotheses validated. SRSD successfully addresses
         structural routing vulnerability while maintaining
         acceptable performance.

HYPOTHESIS 1 (H1)
--------------------------------------------------
Statement: Structural routing predictability is an exploitable
           vulnerability that enables adversarial inference.

Status: validated
Result: H1 validated: Baseline routing shows exploitable predictability
        (entropy 1.23 bits). SRSD increases entropy to 2.45 bits
        (improvement: 1.22 bits).

Evidence:
  - Baseline entropy: 1.2300 bits
  - SRSD entropy: 2.4500 bits
  - Improvement: 1.2200 bits

HYPOTHESIS 2 (H2)
--------------------------------------------------
Statement: SRSD with QKD integration reduces vulnerability
           without significant performance degradation.

Status: validated
Result: H2 validated: SRSD maintains acceptable performance
        (latency overhead: 8.5%, success rate: 99.8%).

Evidence:
  - Latency overhead: 8.50%
  - Baseline success rate: 100.00%
  - SRSD success rate: 99.80%

VALIDATION CRITERIA
--------------------------------------------------
H1 minimum entropy difference: 0.5 bits
H2 maximum latency overhead: 20.0%
H2 minimum success rate: 95%

======================================================================
```

### Critérios de Validação

**H1 é validada quando:**
- Baseline tem entropia baixa (previsível)
- SRSD aumenta entropia em pelo menos 0.5 bits
- Melhoria de entropia > 50%

**H2 é validada quando:**
- Overhead de latência < 20%
- Taxa de sucesso > 95%
- Degradação de sucesso < 5%

---

## Uso Programático

### Exemplo Completo

```python
#!/usr/bin/env python3
"""Exemplo de uso programático do simulador SRSD."""

from src.core import NetworkGraph
from src.routing import BaselineRouter, SRSDRouter, SRSDConfig
from src.adversary import AdversaryCapabilityMetrics, calculate_path_entropy
from src.simulation import Scenario, SimulationRunner

# 1. Criar rede manualmente
print("=== Criando rede ===")
graph = NetworkGraph.create_barabasi_albert(n=30, m=3, seed=42)
print(f"Rede criada: {graph.num_nodes} nós, {graph.num_edges} arestas")

# 2. Testar roteamento baseline
print("\n=== Roteamento Baseline ===")
baseline = BaselineRouter(graph)
for i in range(100):
    baseline.route("n_0", "n_29", f"flow_{i}")

baseline_entropy = calculate_path_entropy(baseline.stats)
print(f"Entropia: {baseline_entropy:.4f} bits")
print(f"Rotas únicas: {baseline.stats.unique_paths}")

# 3. Testar roteamento SRSD
print("\n=== Roteamento SRSD ===")
config = SRSDConfig(
    k_paths=5,
    recurrence_penalty=2.0,
    selection_temperature=1.0,
)
srsd = SRSDRouter(graph, config)
srsd.set_seed(42)

for i in range(100):
    srsd.route("n_0", "n_29", f"flow_{i}")

srsd_entropy = calculate_path_entropy(srsd.stats)
print(f"Entropia: {srsd_entropy:.4f} bits")
print(f"Rotas únicas: {srsd.stats.unique_paths}")

# 4. Comparar
print("\n=== Comparação ===")
improvement = srsd_entropy - baseline_entropy
print(f"Melhoria de entropia: +{improvement:.4f} bits")
print(f"Rotas adicionais: +{srsd.stats.unique_paths - baseline.stats.unique_paths}")

# 5. Analisar capacidade do adversário
print("\n=== Análise de Adversário ===")
metrics = AdversaryCapabilityMetrics(graph)
for flow in baseline.stats.flow_records:
    metrics.add_baseline_flow(flow)
for flow in srsd.stats.flow_records:
    metrics.add_srsd_flow(flow)

comparison = metrics.compare_baseline_vs_srsd()
print(f"Redução de correlação: {comparison['correlation']['improvement']:.2%}")
```

### Usando Cenários

```python
from src.simulation import Scenario, SimulationRunner

# Carregar cenário do arquivo
scenario = Scenario.load("config/scenarios.yaml")

# Ou criar programaticamente
scenario = Scenario(
    name="meu_teste",
    topology=TopologyConfig(type=TopologyType.MESH, rows=4, cols=4),
    traffic=TrafficConfig(num_flows=200),
)

# Executar
runner = SimulationRunner(scenario)
result = runner.run()

# Salvar
filepath = runner.save_results(result)
print(f"Resultados salvos em: {filepath}")
```

---

## Troubleshooting

### Erro: ModuleNotFoundError

```bash
# Certifique-se de estar no diretório correto
cd /caminho/para/simulador

# Instale as dependências
pip install -r requirements.txt
```

### Erro: NetworkX não encontrado

```bash
pip install networkx numpy pyyaml
```

### Testes falhando

```bash
# Verificar versão do Python
python --version  # Deve ser 3.11+

# Reinstalar dependências
pip install -r requirements.txt --force-reinstall
```

### Resultados não salvando

```bash
# Criar diretório de resultados
mkdir -p data/results

# Verificar permissões
chmod 755 data/results
```

### Simulação muito lenta

Reduza o número de fluxos ou nós:

```yaml
# Em config/scenarios.yaml
meu_cenario:
  topology:
    num_nodes: 20  # Reduzir
  traffic:
    num_flows: 100  # Reduzir
```

### Memória insuficiente

Para redes muito grandes:

```python
# Use topologias menores
graph = NetworkGraph.create_barabasi_albert(n=50, m=2)  # em vez de n=1000
```

---

## Próximos Passos

1. **Execute a demo**: `python main.py`
2. **Explore cenários**: `python main.py --list`
3. **Execute testes**: `pytest tests/ -v`
4. **Crie seu cenário**: Edite `config/scenarios.yaml`
5. **Valide hipóteses**: `python main.py --validate`

Para mais detalhes, consulte o código-fonte em `src/` e os testes em `tests/`.
