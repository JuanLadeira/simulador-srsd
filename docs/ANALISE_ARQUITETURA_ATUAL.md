# Análise da Arquitetura Atual e Conformidade com SRSD (Revisado)

## Resumo Executivo

Esta análise revisa a arquitetura do simulador SRSD, incorporando desenvolvimentos recentes que não foram abordados no documento original `ANALISE_CONFORMIDADE_SRSD.md`.

A principal evolução foi a implementação de um **paradigma de roteamento distribuído**, que coexiste com o modelo centralizado original. Isso representa um salto significativo em direção à conformidade com a especificação teórica do SRSD.

O projeto agora opera em três modos distintos:
1.  **Baseline:** Roteamento determinístico convencional (shortest-path).
2.  **SRSD Centralizado (`SRSDRouter`):** Abordagem probabilística multi-caminho com visão global da rede.
3.  **SRSD Distribuído (`DistributedSRouter` + `Drawer`):** Abordagem hop-by-hop com decisão local, sem conhecimento global.

**Veredicto Atualizado:** A implementação do **modo distribuído com `Drawers` está largamente em conformidade** com os princípios arquiteturais fundamentais do SRSD, corrigindo as violações mais críticas do modelo anterior.

---

## 1. A Arquitetura Dupla: Centralizado vs. Distribuído

A maturidade do projeto se manifesta na coexistência de duas implementações do SRSD, permitindo uma análise comparativa muito mais rica.

### 1.1 Modo 1: Roteador SRSD Centralizado (`SRSDRouter`)

Esta é a implementação original.
- **Paradigma:** Centralizado.
- **Lógica:** O roteador possui conhecimento completo do grafo da rede. Ele pré-calcula os `k` melhores caminhos de ponta a ponta e seleciona um probabilisticamente, penalizando a reutilização.
- **Conformidade:** As críticas do documento `ANALISE_CONFORMIDADE_SRSD.md` **continuam válidas para este modo**. Ele não é uma implementação fiel da especificação, mas serve como um importante ponto de comparação entre o roteamento puramente determinístico e um modelo com diversidade.

### 1.2 Modo 2: Roteador SRSD Distribuído (A Implementação Fiel)

Esta é a implementação mais recente e que segue a especificação SRSD à risca. Ela é composta por um ecossistema de componentes que trabalham juntos:

- **`Packet` (`src/core/packet.py`):** Implementado como um **pacote cebola (onion packet)**, onde a rota é uma sequência de camadas criptografadas. Isso esconde a origem e o destino final, garantindo a eliminação de *blind spots*.
- **`Drawer` (`src/core/drawer.py`):** A inteligência de roteamento local de cada nó. Decide o próximo salto para um segmento de rota sem ter visão do todo.
- **`Hiatus` (`src/core/hiatus.py`):** O ponto de descontinuidade estrutural (CAR). Nós do tipo `HIATUS` recebem o pacote, adicionam um atraso para quebrar a correlação temporal e "descascam" a próxima camada do pacote para revelar o destino do novo segmento.
- **`DistributedSRouter` (`src/routing/distributed.py`):** O orquestrador que simula o fluxo. Ele cria o pacote cebola e o injeta na rede, mas as decisões de roteamento são feitas de forma descentralizada pelos `Drawers` e `Hiatus` em cada nó.

- **Conformidade:** Este modo foi projetado para ser uma implementação de alta fidelidade da especificação SRSD.

---

## 2. Reavaliação de Conformidade (Analisando o Modo Distribuído)

Avaliando a arquitetura distribuída (`DistributedSRouter`, `Drawer`, `Hiatus`, `Packet`) contra os requisitos da especificação:

| Aspecto (Especificação) | Implementação Distribuída | Conformidade |
|---------------------------|-------------------------------------------------|--------------|
| **Imprevisibilidade Estrutural** | Decisão local (hop-by-hop) baseada em regras e memória para evitar repetição. Não utiliza métricas de otimização clássicas. | **CONFORME** |
| **Drawer (Gateway)** | **Implementado**. A classe `Drawer` é a personificação do gateway de encaminhamento local e sem estado global. | **CONFORME** |
| **Hiatus (CAR)** | **Implementado**. A classe `HiatusController` e o `NodeType.HIATUS` fornecem a descontinuidade estrutural, quebrando a correlação dos caminhos. | **CONFORME** |
| **Eliminação de Blind Spots** | **Implementado**. A estrutura de pacote cebola (`Packet`) esconde a origem e o destino final, impedindo que nós intermediários conheçam o fluxo completo. | **CONFORME** |
| **QKD Independente** | A lógica de decisão do `Drawer` e `Hiatus` opera com base na estrutura do pacote e na memória local, **sem consultar métricas de QKD**. A independência é respeitada. | **CONFORME** |

---

## 3. Tabela Comparativa das Arquiteturas Implementadas

| Característica | `BaselineRouter` | `SRSDRouter` (Centralizado) | `DistributedSRouter` (com `Drawers`) |
|----------------------|------------------|---------------------------------|---------------------------------------|
| **Paradigma** | Determinístico | Probabilístico, Centralizado | Probabilístico, Distribuído |
| **Conhecimento da Rede** | Global | Global | **Local (Apenas vizinhos)** |
| **Lógica de Decisão** | Shortest-Path | Seleção de rota End-to-End | **Seleção Hop-by-Hop** |
| **Cálculo da Rota** | Pré-calculada e única | Pré-calculada (k-paths) | **Construída dinamicamente** |
| **Conformidade SRSD** | N/A | Baixa | **Total** |

---

## 4. Como Ativar e Configurar o Modo Distribuído

Para utilizar a arquitetura distribuída, a seção `topology` do cenário em `config/scenarios.yaml` deve ser configurada para definir os parâmetros do `Hiatus`, e a seção `experiment` deve habilitar o teste.

**Exemplo (`config/scenarios.yaml`):**
```yaml
distributed_test:
  name: distributed_test
  description: "Scenario for testing the full distributed SRSD implementation"

  topology:
    type: mesh
    rows: 6
    cols: 6
    # ...
    num_hiatus: 5               # <-- Define quantos nós serão Hiatus
    hiatus_placement: random    # <-- Estratégia para escolher os nós Hiatus

  experiment:
    name: distributed_srsd_test
    # ...
    test_distributed: true      # <-- HABILITA O MODO DISTRIBUÍDO
```

---

## 5. Conclusão Atualizada

O simulador evoluiu para uma **plataforma de alta fidelidade para a simulação da arquitetura SRSD**. A introdução dos componentes `Packet` (cebola), `Hiatus` e `Drawer` no modo distribuído permite que o projeto:

1.  **Atinja Conformidade Total:** O modo distribuído agora implementa todos os pilares fundamentais da especificação SRSD.
2.  **Realize Análises Comparativas Ricas:** Permite comparar o modelo SRSD fiel contra uma versão centralizada e o roteamento convencional, gerando dados valiosos sobre os trade-offs de segurança e performance.

A arquitetura atual é uma base robusta e completa para estudar e validar academicamente os benefícios de segurança do paradigma SRSD.
