# Guia Completo: Fluxo de Simulação do SRSD Simulator

Este documento explica detalhadamente como o simulador funciona, desde a configuração de cenários até a execução e coleta de resultados.

---

## 1. Visão Geral do Projeto

O SRSD Simulator valida duas hipóteses:

- **H1**: A previsibilidade estrutural de roteamento convencional é uma vulnerabilidade explorável por adversários
- **H2**: O SRSD integrado com indicadores QKD reduz essa vulnerabilidade sem degradação significativa de desempenho

### Estrutura de Módulos

```
src/
├── core/           # Modelagem de rede (grafo, nós, arestas)
├── routing/        # Algoritmos: baseline (shortest-path) e SRSD
├── adversary/      # Simulação de adversário e métricas de ataque
├── qkd/            # Abstração de canais QKD (Quantum Key Distribution)
├── simulation/     # Framework de execução de cenários
└── analysis/       # Comparação e validação de hipóteses
```

---

## 2. Fluxo Completo de Execução

### 2.1 Diagrama de Fluxo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FLUXO DE SIMULAÇÃO                                │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐
    │ config/          │
    │ scenarios.yaml   │  ← Arquivo de configuração YAML
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ main.py          │  ← Ponto de entrada
    │ load_scenarios() │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Scenario.        │  ← Deserializa configuração
    │ from_dict()      │     para objetos Python
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ SimulationRunner │  ← Orquestrador principal
    │ .initialize()    │
    └────────┬─────────┘
             │
             ├──────────────────────────────────────────┐
             ▼                                          ▼
    ┌──────────────────┐                      ┌──────────────────┐
    │ scenario.        │                      │ scenario.        │
    │ build_topology() │                      │ generate_traffic │
    │                  │                      │ _pairs()         │
    └────────┬─────────┘                      └────────┬─────────┘
             │                                         │
             │  Cria NetworkGraph                      │  Gera lista de
             │  (mesh, barabasi,                       │  (origem, destino)
             │   watts-strogatz)                       │
             │                                         │
             └──────────────────┬──────────────────────┘
                                │
                                ▼
                    ┌──────────────────┐
                    │ SimulationRunner │
                    │ .run()           │
                    └────────┬─────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ BaselineRouter  │ │ SRSDRouter      │ │ QKD-SRSD        │
│ (se habilitado) │ │ (se habilitado) │ │ (se habilitado) │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         │   Para cada par (src, dst):          │
         │   router.route(src, dst)             │
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ FlowRecord       │  ← Registro de cada fluxo:
                    │                  │     path, latency, hops
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ MetricsCollector │  ← Coleta estatísticas
                    │ AdversaryMetrics │     e métricas de adversário
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ ExperimentResult │  ← Resultado consolidado
                    │ .save()          │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ data/results/    │
                    │ {scenario}_{ts}  │  ← Arquivo JSON de saída
                    │ .json            │
                    └──────────────────┘
```

---

## 3. Configuração de Cenários (scenarios.yaml)

O arquivo `config/scenarios.yaml` define todos os cenários de teste. Cada cenário tem três seções principais:

### 3.1 Exemplo Completo: Cenário `small_mesh`

```yaml
small_mesh:
  name: small_mesh
  description: "Small 4x4 mesh network for basic SRSD validation"

  topology:
    type: mesh           # Tipo de topologia
    rows: 4              # Linhas da grade
    cols: 4              # Colunas da grade
    bidirectional: true  # Arestas bidirecionais
    qkd_enabled: false   # Sem QKD neste cenário
    seed: 42             # Semente para reprodutibilidade

  traffic:
    pattern: uniform     # Padrão de tráfego
    num_flows: 500       # Número de fluxos a simular
    flow_rate: 10.0      # Fluxos por segundo (simulado)
    seed: 42

  experiment:
    name: small_mesh_test
    duration: 50.0       # Duração total da simulação (segundos)
    warmup: 5.0          # Período de aquecimento (excluído dos resultados)
    test_baseline: true  # Testar algoritmo baseline
    test_srsd: true      # Testar algoritmo SRSD
    test_srsd_qkd: false # Não testar SRSD com QKD
    srsd_k_paths: 3      # Número de caminhos candidatos
    srsd_recurrence_penalty: 2.0  # Penalidade por repetição
    output_dir: data/results
```

---

## 4. Parâmetros de Configuração Detalhados

### 4.1 Seção `topology` - Configuração da Rede

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `type` | string | Tipo de topologia: `mesh`, `barabasi_albert`, `watts_strogatz`, `random` |
| `rows` | int | **Mesh**: número de linhas da grade |
| `cols` | int | **Mesh**: número de colunas da grade |
| `num_nodes` | int | Número de nós (para topologias não-mesh) |
| `ba_m` | int | **Barabási-Albert**: arestas por novo nó (define conectividade) |
| `ws_k` | int | **Watts-Strogatz**: vizinhos iniciais por nó |
| `ws_p` | float | **Watts-Strogatz**: probabilidade de reconexão (0-1) |
| `bidirectional` | bool | Se true, cada aresta tem sentido duplo |
| `qkd_enabled` | bool | Habilita canais QKD nas arestas |
| `qkd_coverage` | float | Fração de arestas com QKD (0-1) |
| `seed` | int | Semente para geração reprodutível |

#### Tipos de Topologia

**Mesh (Grade)**
```
Rede em grade regular. Para 4x4:
n_0_0 ─ n_0_1 ─ n_0_2 ─ n_0_3
  │       │       │       │
n_1_0 ─ n_1_1 ─ n_1_2 ─ n_1_3
  │       │       │       │
n_2_0 ─ n_2_1 ─ n_2_2 ─ n_2_3
  │       │       │       │
n_3_0 ─ n_3_1 ─ n_3_2 ─ n_3_3

Total de nós: rows × cols = 16
```

**Barabási-Albert (Scale-Free)**
```
Rede que simula a Internet. Novos nós se conectam
preferencialmente a nós com muitas conexões.
- ba_m=2: cada novo nó conecta a 2 existentes
- Resulta em poucos hubs altamente conectados
```

**Watts-Strogatz (Small-World)**
```
Rede com propriedades de "mundo pequeno".
- ws_k=4: cada nó conecta a 4 vizinhos
- ws_p=0.15: 15% das arestas são reconectadas aleatoriamente
- Combina clustering alto com caminhos curtos
```

---

### 4.2 Seção `traffic` - Geração de Tráfego

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `pattern` | string | Padrão de tráfego: `uniform`, `hotspot`, `burst`, `sequential`, `realistic` |
| `num_flows` | int | Quantidade total de fluxos a simular |
| `flow_rate` | float | Taxa de fluxos por segundo (para temporização) |
| `hotspot_nodes` | int | **Hotspot**: número de nós concentradores |
| `hotspot_concentration` | float | **Hotspot**: fração do tráfego nos hotspots (0-1) |
| `burst_size` | int | **Burst**: fluxos por rajada |
| `burst_interval` | float | **Burst**: intervalo entre rajadas (segundos) |
| `seed` | int | Semente para reprodutibilidade |

#### Padrões de Tráfego

**uniform** - Tráfego Uniforme
```
Origem e destino escolhidos aleatoriamente entre todos os nós.
Cada nó tem probabilidade igual de ser origem ou destino.
Uso: Teste básico de diversidade de rotas.
```

**hotspot** - Tráfego Concentrado
```
Tráfego concentrado em poucos nós (hotspots).
- hotspot_nodes=5: 5 nós são hotspots
- hotspot_concentration=0.6: 60% do tráfego envolve hotspots
Uso: Simula servidores populares ou data centers.
```

**sequential** - Tráfego Sequencial
```
Pares origem-destino em sequência determinística:
  Flow 0: n_0 → n_1
  Flow 1: n_1 → n_2
  Flow 2: n_2 → n_3
  ...
Uso: Teste de adversário (padrão previsível).
```

**burst** - Tráfego em Rajadas
```
Múltiplos fluxos com mesmo par origem-destino.
- burst_size=20: cada rajada tem 20 fluxos idênticos
Uso: Simula transferências de arquivos grandes.
```

**realistic** - Tráfego Misto
```
Combinação realista:
- 40% uniform
- 30% hotspot
- 20% repetido (mesmos pares)
- 10% burst
Uso: Aproximação de tráfego real de Internet.
```

---

### 4.3 Seção `experiment` - Parâmetros de Execução

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `name` | string | Nome do experimento (para identificação) |
| `duration` | float | Duração simulada em segundos |
| `warmup` | float | Período de aquecimento (excluído das métricas) |
| `test_baseline` | bool | Executar algoritmo baseline (shortest-path) |
| `test_srsd` | bool | Executar algoritmo SRSD |
| `test_srsd_qkd` | bool | Executar SRSD com integração QKD |
| `srsd_k_paths` | int | Número de caminhos candidatos para SRSD |
| `srsd_recurrence_penalty` | float | Peso da penalidade por reutilização de caminho |
| `srsd_temperature` | float | Temperatura para seleção probabilística (softmax) |
| `output_dir` | string | Diretório para salvar resultados |

#### Parâmetros do SRSD

**srsd_k_paths** (default: 5)
```
Número de caminhos alternativos considerados.
- Valor baixo (2-3): menos overhead, menos diversidade
- Valor alto (5-10): mais diversidade, mais processamento
```

**srsd_recurrence_penalty** (default: 2.0)
```
Multiplicador de penalidade para caminhos usados recentemente.
- 1.0: penalidade básica
- 2.0: penalidade moderada (recomendado)
- 3.0+: evita fortemente repetição
```

**srsd_temperature** (default: 1.0)
```
Controla aleatoriedade na seleção de caminhos.
- < 1.0: mais determinístico (prefere melhor caminho)
- 1.0: balanceado
- > 1.0: mais aleatório (mais diversidade)
```

---

## 5. O que Acontece Durante uma Simulação

### 5.1 Fase de Inicialização

1. **Carregamento do Cenário** (`main.py:35-52`)
   - Lê `config/scenarios.yaml`
   - Converte YAML para objeto `Scenario`

2. **Construção da Topologia** (`scenario.py:144-187`)
   - Cria `NetworkGraph` baseado no tipo
   - Adiciona nós com coordenadas
   - Cria arestas com atributos (peso, latência)

3. **Geração de Tráfego** (`scenario.py:205-287`)
   - Gera lista de pares `(origem, destino)`
   - Aplica o padrão de tráfego configurado

4. **Inicialização de Roteadores** (`runner.py:145-179`)
   - Cria `BaselineRouter` (se habilitado)
   - Cria `SRSDRouter` com configurações
   - Inicializa observador de adversário

### 5.2 Fase de Execução

Para cada algoritmo habilitado (baseline, srsd, srsd_qkd):

```python
for (src, dst) in traffic_pairs:
    flow = router.route(src, dst, flow_id)
    observer.observe_flow(flow)  # Adversário observa
```

**Algoritmo Baseline** (`baseline.py:173-213`):
1. Verifica cache de caminhos
2. Se não existe, calcula shortest-path (Dijkstra)
3. Armazena no cache (determinístico)
4. Retorna sempre o mesmo caminho para mesmo par

**Algoritmo SRSD** (`srsd.py:87-134`):
1. Obtém k caminhos candidatos
2. Calcula score de cada caminho:
   - Custo base (comprimento)
   - Penalidade de memória (evita repetição)
   - Exposição das arestas
   - Risco QKD (se habilitado)
3. Seleciona probabilisticamente (softmax)
4. Registra uso na memória de rotas

### 5.3 Fase de Coleta de Métricas

Métricas coletadas por algoritmo:

| Métrica | Descrição | Fórmula |
|---------|-----------|---------|
| `successful_flows` | Fluxos roteados com sucesso | Contagem |
| `failed_flows` | Fluxos sem caminho disponível | Contagem |
| `avg_latency` | Latência média | Σ latência / flows |
| `avg_hops` | Saltos médios por caminho | Σ hops / flows |
| `path_entropy` | Entropia de Shannon dos caminhos | -Σ p(path) × log₂(p(path)) |
| `unique_paths` | Caminhos distintos utilizados | Contagem |

### 5.4 Fase de Comparação

Métricas comparativas (Baseline vs SRSD):

```
entropy_improvement_pct = (srsd_entropy - baseline_entropy) / baseline_entropy × 100
diversity_improvement_pct = (srsd_unique - baseline_unique) / baseline_unique × 100
latency_overhead_pct = (srsd_latency - baseline_latency) / baseline_latency × 100
```

---

## 6. Exemplo Prático: Cenário `small_mesh`

### 6.1 Configuração

```yaml
small_mesh:
  topology:
    type: mesh
    rows: 4
    cols: 4
    bidirectional: true
  traffic:
    pattern: uniform
    num_flows: 500
  experiment:
    test_baseline: true
    test_srsd: true
    srsd_k_paths: 3
```

### 6.2 O que é Criado

**Topologia:**
- 16 nós (4×4)
- 48 arestas bidirecionais (24 pares)
- Cada nó interno tem 4 vizinhos

**Tráfego:**
- 500 pares (origem, destino) aleatórios
- Distribuição uniforme entre todos os 16 nós

### 6.3 Resultado Esperado (Exemplo Real)

```json
{
  "baseline": {
    "successful_flows": 100,
    "avg_latency": 2.04,
    "path_entropy": 5.54,
    "unique_paths": 53
  },
  "srsd": {
    "successful_flows": 100,
    "avg_latency": 2.16,
    "path_entropy": 5.93,
    "unique_paths": 69
  },
  "comparison": {
    "entropy_improvement_pct": 6.99,
    "diversity_improvement_pct": 30.19,
    "latency_overhead_pct": 5.88
  }
}
```

**Interpretação:**
- SRSD aumentou entropia em ~7% (menos previsível)
- SRSD usou 30% mais caminhos únicos
- Overhead de latência foi apenas ~6% (aceitável)

---

## 7. Métricas de Adversário

O simulador inclui um adversário estrutural passivo que observa o tráfego:

### 7.1 Métricas Coletadas

| Métrica | Descrição |
|---------|-----------|
| `correlation` | Capacidade de correlacionar entrada/saída |
| `fingerprinting` | Taxa de identificação de pares por padrão |
| `predictability` | Entropia e recorrência observadas |

### 7.2 Exemplo de Resultado

```json
"adversary": {
  "correlation": {
    "baseline_accuracy": 0.47,
    "srsd_accuracy": 0.47,
    "improvement": 0.0
  },
  "fingerprinting": {
    "baseline_identification_rate": 0.76,
    "srsd_identification_rate": 0.71,
    "improvement": 0.05
  },
  "predictability": {
    "baseline_recurrence": 1.0,
    "srsd_recurrence": 0.78,
    "recurrence_reduction": 0.22
  }
}
```

---

## 8. Como Executar Testes

### Comandos Básicos

```bash
# Demo rápida (rede 3x3, 100 fluxos)
python main.py

# Listar cenários disponíveis
python main.py --list

# Executar cenário específico
python main.py --scenario small_mesh
python main.py --scenario adversary_test

# Executar todos os cenários
python main.py --all

# Validar hipóteses com resultados existentes
python main.py --validate
```

### Com Taskipy (se configurado)

```bash
task run              # Demo rápida
task scenario small_mesh
task all              # Todos os cenários
task validate         # Validação
task test             # Testes unitários
```

---

## 9. Criando Novos Cenários

Adicione ao `config/scenarios.yaml`:

```yaml
meu_cenario:
  name: meu_cenario
  description: "Descrição do meu cenário"

  topology:
    type: barabasi_albert
    num_nodes: 30
    ba_m: 3
    bidirectional: true
    qkd_enabled: true
    qkd_coverage: 0.5
    seed: 123

  traffic:
    pattern: hotspot
    num_flows: 1000
    hotspot_nodes: 3
    hotspot_concentration: 0.7
    seed: 123

  experiment:
    name: teste_meu_cenario
    duration: 60.0
    warmup: 5.0
    test_baseline: true
    test_srsd: true
    test_srsd_qkd: true
    srsd_k_paths: 5
    srsd_recurrence_penalty: 2.5
    output_dir: data/results
```

Execute com:
```bash
python main.py --scenario meu_cenario
```

---

## 10. Resumo do Fluxo

```
1. YAML → Scenario object
2. Scenario → NetworkGraph (topologia)
3. Scenario → Lista de pares (tráfego)
4. Para cada algoritmo:
   - Para cada par (src, dst):
     - Router calcula caminho
     - FlowRecord registra resultado
     - Adversário observa
5. Métricas são agregadas
6. Comparação baseline vs SRSD
7. Resultado salvo em JSON
```

A validação de H1 e H2 usa esses resultados para verificar:
- **H1**: Baseline tem baixa entropia → explorável
- **H2**: SRSD aumenta entropia sem degradar muito a latência
