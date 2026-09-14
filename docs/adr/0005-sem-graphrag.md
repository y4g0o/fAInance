# ADR 0005 — Sem GraphRAG (grafo de conhecimento como tabela, não como framework)

**Data:** 2026-08-05 · **Estado:** Aceita

## Contexto

O sistema vai indexar PDFs, notas fiscais, contratos, garantias e livros. GraphRAG
promete responder perguntas que ligam entidades ("quais contratos citam a mesma
empresa do processo?"). Avaliados: microsoft/graphrag, LightRAG, Graphiti/Neo4j.

## Decisão

**Sem GraphRAG.** Busca híbrida (BM25 via FTS5 + vetores densos, fundidos por RRF) e,
para as perguntas de múltiplos saltos, **entidades canônicas em tabelas
relacionais** — `entidades` + `documento_entidade` — extraídas na mesma chamada de
LLM que já vai gerar os metadados do documento. Multi-hop passa a ser um `JOIN`.

## Por quê — os números

- **O ganho é estreito.** GraphRAG-Bench (ICLR'26): em recuperação factual de um
  salto, chunks marcam F1 **64,8** contra **63,0** do melhor método de grafo. O ganho
  aparece em multi-hop (70,3 vs 67,0) e em sumarização (+13 pts). Mas as perguntas
  reais aqui — "qual a garantia da geladeira", "quanto gastei em farmácia" — são de
  um salto ou são SQL.
- **O custo de construção é proibitivo neste hardware.** Extração de entidades e
  relações custa ~10k tokens de LLM por documento; num 8B na RTX 4060 Ti isso dá
  ~40–60 s/documento, ou **55–85 horas de GPU** para 5.000 documentos — repetidas a
  cada reindexação, na mesma GPU que precisa rodar o assistente.
- **A atualização incremental é o assassino silencioso.** Documento novo altera
  comunidades e resumos de comunidade. Numa base que cresce com boleto e nota fiscal
  todo mês, isso se paga eternamente.
- **A referência de grafo temporal não entrega o que promete.** Graphiti marca **7%**
  em consolidação de fato no MemoryAgentBench — o grafo não está resolvendo conflito
  na prática.
- **Custo operacional:** Graphiti exige Neo4j (JVM) ou FalkorDB; o backend embutido
  que ele oferecia (Kuzu) está **arquivado**.

## Consequências

Perguntas de síntese sobre o corpus todo ficam piores do que ficariam com hierarquia
de resumos. Mitigação prevista: sumarização hierárquica offline (algoritmo tipo
RAPTOR, ~150 linhas, em job noturno) apenas para documentos acima de ~50 páginas.

*Grafo de conhecimento como tabelas relacionais é a versão de dez anos; grafo como
framework é a versão de dezoito meses.*

## Gatilho de revisão

Reabrir se, com busca híbrida + reranking já em produção, **mais de 20% das
perguntas reais** (medidas num log de perguntas, não estimadas) exigirem ligar três
ou mais entidades e o `JOIN` sobre a tabela de entidades se mostrar insuficiente.
