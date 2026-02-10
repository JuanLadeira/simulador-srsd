# Analise de Conformidade: Simulador vs Especificacao SRSD

## Resumo Executivo

| Aspecto | Status | Criticidade |
|---------|--------|-------------|
| Imprevisibilidade Estrutural | PARCIAL | ALTA |
| Drawer (Gateway) | NAO IMPLEMENTADO | CRITICA |
| Hiatus (CAR) | NAO IMPLEMENTADO | CRITICA |
| Eliminacao de Blind Spots | NAO IMPLEMENTADO | ALTA |
| QKD Obrigatorio | PARCIAL (opcional) | ALTA |
| QKD Independente | VIOLADO | ALTA |

**Veredicto: O simulador atual NAO esta em conformidade com a especificacao SRSD.**

---

## 1. Analise Detalhada por Requisito

### 1.1 Imprevisibilidade Estrutural

**Especificacao:**
> "Seu objetivo central e eliminar padroes de trafego repetitivos durante a transmissao de dados entre um remetente e um destinatario, priorizando a nao repeticao deterministica de percursos ao longo do tempo."

**Implementacao Atual (srsd.py:136-169):**
```python
def _get_candidate_paths(self, source: str, destination: str):
    shortest = self.graph.shortest_path(source, destination)  # <-- USA SHORTEST PATH
    candidates = self.graph.k_shortest_paths(source, destination, k=self.config.k_paths)
```

**Problemas:**
1. USA metricas classicas de otimizacao (shortest path, k-shortest paths)
2. A selecao e probabilistica mas baseada em CAMINHOS OTIMOS
3. Penaliza repeticao mas nao BLOQUEIA politicamente

**Status: PARCIAL**
- Implementa diversidade de caminhos
- NAO elimina metricas classicas de otimizacao
- Repeticao e PENALIZADA, nao BLOQUEADA

---

### 1.2 Drawer (Gateway de Encaminhamento Seguro)

**Especificacao:**
> "O Drawer atua como o gateway de encaminhamento seguro, operando como elemento arquitetural responsavel por conduzir o processo de encaminhamento a partir do estado operacional momentaneo da infraestrutura, assegurando a nao repeticao deterministica dos percursos sem recorrer a rotas pre-definidas, metricas classicas de otimizacao ou conhecimento global da topologia."

**Requisitos do Drawer:**
| Requisito | Implementado? |
|-----------|---------------|
| Estado operacional momentaneo | PARCIAL |
| Sem rotas pre-definidas | NAO |
| Sem metricas classicas de otimizacao | NAO |
| Sem conhecimento global da topologia | NAO |

**Implementacao Atual:**
```python
class SRSDRouter(Router):
    def __init__(self, graph: NetworkGraph, ...):
        self.graph = graph  # <-- CONHECIMENTO GLOBAL DA TOPOLOGIA
```

**Problemas Criticos:**
1. O roteador tem ACESSO TOTAL ao grafo da rede
2. Usa `graph.shortest_path()` - conhecimento global
3. Usa `graph.k_shortest_paths()` - calculo centralizado
4. NAO existe entidade "Drawer" na arquitetura

**Status: NAO IMPLEMENTADO**

---

### 1.3 Hiatus (Conversores de Alteracao de Rota - CAR)

**Especificacao:**
> "A arquitetura incorpora os Hiatus, tambem denominados Conversores de Alteracao de Rota (CAR), que funcionam como pontos intermediarios de transicao estrutural. Cada Hiatus introduz uma descontinuidade logica no encaminhamento, ampliando significativamente o espaco de possibilidades de percurso."

**Implementacao Atual:**
- NAO EXISTE conceito de Hiatus no codigo
- NAO EXISTE NodeType.HIATUS ou similar
- Todos os nos sao tratados igualmente

**Verificacao em node.py:**
```python
class NodeType(Enum):
    ENDPOINT = "endpoint"
    ROUTER = "router"
    QKD_ENABLED = "qkd_enabled"
    # NAO EXISTE: HIATUS ou CAR
```

**Status: NAO IMPLEMENTADO**

---

### 1.4 Eliminacao de Blind Spots

**Especificacao:**
> "O SRSD elimina a existencia de Blind Spots de entrada e saida. Os mesmos canais fisicos ou logicos sao utilizados indistintamente para recepcao e encaminhamento de dados, impossibilitando a identificacao de pontos fixos de origem ou destino por meio de analise externa de trafego."

**Implementacao Atual:**
```python
@dataclass
class FlowRecord:
    source: str       # <-- ORIGEM IDENTIFICAVEL
    destination: str  # <-- DESTINO IDENTIFICAVEL
    path: List[str]   # <-- CAMINHO COMPLETO VISIVEL
```

**Problemas:**
1. Origem e destino sao CLARAMENTE IDENTIFICADOS
2. O caminho completo e registrado
3. NAO ha mecanismo de ofuscacao de entrada/saida
4. Adversario pode facilmente correlacionar

**Status: NAO IMPLEMENTADO**

---

### 1.5 QKD Obrigatorio

**Especificacao:**
> "O SRSD adota obrigatoriamente mecanismos de Distribuicao Quantica de Chaves (QKD) como camada de seguranca criptografica."

**Implementacao Atual (scenarios.yaml):**
```yaml
small_mesh:
  topology:
    qkd_enabled: false  # <-- QKD DESABILITADO
```

```python
# scenario.py
qkd_enabled: bool = False  # <-- DEFAULT E FALSE
```

**Problemas:**
1. QKD e OPCIONAL (deveria ser obrigatorio)
2. Maioria dos cenarios NAO usa QKD
3. Permite execucao sem qualquer QKD

**Status: PARCIAL (implementado mas opcional)**

---

### 1.6 QKD Independente da Logica de Encaminhamento

**Especificacao:**
> "A camada de QKD opera de forma independente da logica estrutural de encaminhamento do SRSD, nao interferindo na selecao de percursos nem introduzindo conhecimento antecipado da rota completa."

**Implementacao Atual (srsd.py:250-254):**
```python
# QKD risk penalty (if enabled)
if self.config.use_qkd_indicators:
    qkd_risk = self._get_qkd_risk(edge)
    if qkd_risk > self.config.qkd_threshold:
        score += qkd_risk * self.config.qkd_risk_penalty  # <-- QKD INTERFERE NA ROTA
```

**Problemas Criticos:**
1. QKD INFLUENCIA diretamente a selecao de rotas
2. `qkd_risk_penalty` penaliza caminhos baseado em estado QKD
3. VIOLA a independencia especificada

**Status: VIOLADO**

---

## 2. Tabela Comparativa: Especificacao vs Implementacao

| Aspecto (Documento) | Especificacao | Implementacao Atual | Conformidade |
|---------------------|---------------|---------------------|--------------|
| Escolha de rota | Nao deterministica | Probabilistica sobre caminhos otimos | PARCIAL |
| Repeticao | Politicamente bloqueada | Penalizada (nao bloqueada) | NAO |
| Seguranca | Dependente de arquitetura | Dependente de algoritmo | NAO |
| Entropia | Estrutural e estavel | Estatistica (via softmax) | NAO |
| Drawer | Gateway local sem visao global | Roteador centralizado com grafo completo | NAO |
| Hiatus | Pontos de transicao estrutural | Nao existe | NAO |
| Blind Spots | Eliminados | Origem/destino visiveis | NAO |
| QKD | Obrigatorio e independente | Opcional e interfere na rota | NAO |

---

## 3. Problemas Arquiteturais Fundamentais

### 3.1 Modelo Centralizado vs Distribuido

**Especificacao:** Decisoes locais baseadas em estado momentaneo
**Implementacao:** Roteador tem visao global do grafo

```
ESPECIFICACAO SRSD:               IMPLEMENTACAO ATUAL:

    [Drawer A]                         [Router Central]
        |                                    |
    conhece apenas                    conhece TODA a rede
    vizinhos diretos                         |
        |                              NetworkGraph
        v                              (grafo completo)
    decide localmente                        |
                                       shortest_path()
                                       k_shortest_paths()
```

### 3.2 Ausencia de Descontinuidade Estrutural

O Hiatus deveria criar "cortes" logicos no caminho:

```
ESPECIFICACAO:                    IMPLEMENTACAO:

A -> B -> [HIATUS] -> C -> D      A -> B -> C -> D
         ^                        (caminho continuo)
         |
    descontinuidade               sem conceito de
    logica                        transicao estrutural
```

### 3.3 Fluxo de Informacao Invertido

**SRSD Real:** Cada no decide localmente para onde encaminhar
**Simulador:** Rota completa calculada ANTES do encaminhamento

---

## 4. Recomendacoes para Conformidade

### 4.1 Mudancas Criticas (Arquiteturais)

1. **Implementar Drawer**
   - Cada no deve ter um Drawer local
   - Drawer conhece APENAS vizinhos diretos
   - Decisao de encaminhamento hop-by-hop

2. **Implementar Hiatus**
   - Criar NodeType.HIATUS
   - Hiatus recebe pacote e REDEFINE proximo salto
   - Nao preserva informacao de origem

3. **Eliminar Conhecimento Global**
   - Remover `self.graph` do roteador
   - Substituir por interface de vizinhanca local

### 4.2 Mudancas Importantes (Logica)

4. **Bloquear Repeticao (nao apenas penalizar)**
   ```python
   # ATUAL (errado):
   score += memory_penalty * self.config.recurrence_penalty

   # CORRETO:
   if path in recently_used:
       return None  # BLOQUEIO, nao penalidade
   ```

5. **QKD Obrigatorio**
   ```python
   # scenario.py
   qkd_enabled: bool = True  # DEFAULT DEVE SER TRUE
   ```

6. **QKD Independente**
   - Remover `qkd_risk_penalty` da selecao de rotas
   - QKD apenas para criptografia, nao para roteamento

### 4.3 Mudancas na Arquitetura de Dados

7. **Ofuscar Origem/Destino**
   ```python
   @dataclass
   class FlowRecord:
       # Remover source/destination explicitos
       entry_point: str  # Ponto de entrada na rede
       exit_point: str   # Ponto de saida (nao destino final)
   ```

---

## 5. Conclusao

O simulador atual implementa um **sistema de roteamento multi-path com diversidade probabilistica**, que e fundamentalmente diferente do **SRSD especificado**.

**Diferencas Conceituais:**

| Conceito | SRSD (Documento) | Simulador (Atual) |
|----------|------------------|-------------------|
| Paradigma | Distribuido, local | Centralizado, global |
| Decisao | Hop-by-hop | End-to-end |
| Repeticao | Bloqueio politico | Penalizacao estatistica |
| Seguranca | Arquitetural | Algoritmica |

**Para estar em conformidade, o simulador precisaria ser fundamentalmente reescrito**, implementando:
1. Roteamento distribuido (cada no decide localmente)
2. Conceito de Drawer e Hiatus
3. Bloqueio de repeticao (nao penalizacao)
4. Eliminacao de blind spots
5. QKD obrigatorio e independente

O codigo atual serve como **baseline comparativo** para demonstrar H1 (vulnerabilidade de roteamento convencional), mas **NAO implementa o SRSD real** conforme especificado no documento.
