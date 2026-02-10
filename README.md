# SRSD Simulator

Simulador de rede para validação experimental do **SRSD (Sistema de Roteamento Seguro Distribuído)**.

## Objetivo

Demonstrar experimentalmente que:
- **H1**: A previsibilidade estrutural de roteamento convencional é uma vulnerabilidade explorável por adversários
- **H2**: O SRSD integrado com indicadores QKD reduz essa vulnerabilidade sem degradação significativa de desempenho

## Estrutura do Projeto

```
simulador/
├── src/
│   ├── core/           # Modelagem de rede (grafo, nós, arestas)
│   ├── routing/        # Algoritmos de roteamento (baseline, SRSD)
│   ├── adversary/      # Modelagem de adversário e métricas
│   ├── qkd/            # Abstração de canais QKD
│   ├── simulation/     # Framework de simulação
│   └── analysis/       # Análise comparativa e validação
├── tests/              # Testes automatizados
├── data/
│   ├── topologies/     # Topologias de rede
│   └── results/        # Resultados dos experimentos
├── config/
│   └── scenarios.yaml  # Configuração de cenários
├── main.py             # Ponto de entrada
└── requirements.txt    # Dependências
```

## Instalação

```bash
# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt
```

## Uso Rápido

```bash
# Executar demonstração rápida
python main.py

# Listar cenários disponíveis
python main.py --list

# Executar cenário específico
python main.py --scenario small_mesh

# Executar todos os cenários
python main.py --all

# Validar hipóteses com resultados existentes
python main.py --validate
```

## Cenários Disponíveis

| Cenário | Descrição | Topologia |
|---------|-----------|-----------|
| `small_mesh` | Rede mesh pequena para testes básicos | 4x4 mesh |
| `medium_scalefree` | Rede scale-free tipo Internet | Barabási-Albert 50 nós |
| `small_world` | Rede small-world | Watts-Strogatz 40 nós |
| `qkd_network` | Rede com cobertura QKD parcial | Barabási-Albert 30 nós |
| `large_scale` | Teste de escala grande | Barabási-Albert 100 nós |
| `adversary_test` | Foco em análise de adversário | 5x5 mesh |

## Testes

```bash
# Executar todos os testes
pytest tests/ -v

# Executar com cobertura
pytest tests/ --cov=src --cov-report=html
```

## Métricas Coletadas

| Métrica | Hipótese | Descrição |
|---------|----------|-----------|
| Entropia de caminhos | H1 | Diversidade de rotas utilizadas |
| Taxa de repetição | H1 | Frequência de reuso de rotas |
| Correlação do adversário | H1, H2 | Sucesso em inferir padrões |
| Latência média | H2 | Impacto no desempenho |
| Taxa de sucesso | H2 | Confiabilidade do roteamento |

## Arquitetura

### Core (`src/core/`)
- `graph.py`: Grafo dirigido com suporte a NetworkX
- `node.py`: Nós de rede com estatísticas de tráfego
- `edge.py`: Arestas com atributos estruturais (recorrência, exposição)

### Routing (`src/routing/`)
- `baseline.py`: Roteamento determinístico shortest-path (controle)
- `srsd.py`: Algoritmo SRSD com seleção não-repetitiva
- `route_memory.py`: Memória estrutural para diversidade de rotas

### Adversary (`src/adversary/`)
- `observer.py`: Adversário estrutural passivo
- `metrics.py`: Métricas de capacidade de inferência

### QKD (`src/qkd/`)
- `channel.py`: Abstração de canal QKD
- `risk_indicator.py`: Indicadores de risco para roteamento

### Simulation (`src/simulation/`)
- `scenario.py`: Definição de cenários experimentais
- `runner.py`: Executor de experimentos
- `collector.py`: Coleta sistemática de métricas

### Analysis (`src/analysis/`)
- `comparator.py`: Análise comparativa baseline vs SRSD
- `validator.py`: Validação formal de H1 e H2

## Exemplo de Resultado

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
Path Entropy (bits)             0.0000       1.5849      +1.5849
Unique Paths                         1            4           +3
Avg Latency (ms)                10.00        12.50       +2.50
Success Rate (%)                100.0        100.0

INTERPRETATION:
  + SRSD increased path entropy by 1.5849 bits
    -> Routing is LESS predictable to adversaries
  + SRSD used 3 more unique paths
    -> Greater path diversity achieved
  + Latency overhead (25.0%) may need optimization
```

## Licença

Este projeto é parte de pesquisa acadêmica sobre roteamento seguro.
