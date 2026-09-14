# ADR 0003 — Sem framework de agente nem de RAG

**Data:** 2026-08-05 · **Estado:** Aceita

## Contexto

O sistema precisa de tool calling, memória persistente e — no futuro — recuperação
sobre documentos. A tentação é adotar um framework pronto. Três pesquisas
independentes avaliaram os candidatos com dados do GitHub verificados em 05/08/2026.

## Decisão

**Nenhum framework de agente, de RAG ou de memória.** Código próprio pequeno sobre
a API HTTP do Ollama, isolada atrás de uma interface de ~30 linhas.

## Por quê — evidência, não gosto

Estabilidade de API é o critério dominante para dez anos, e é justamente onde essa
categoria falha:

- **LlamaIndex** segue em `0.14.x` depois de ~4 anos. 0.x perpétuo é churn
  institucionalizado, com namespace fragmentado em centenas de pacotes.
- **Haystack** lançou **v3.0.0 em jul/2026** — segunda reescrita depois do 1.x→2.x.
  Ironicamente é o mais bem mantido do grupo, o que mostra que o problema não é
  desleixo: é a natureza da categoria.
- **RAGFlow**: 1.896 issues abertas, e exige Elasticsearch + MySQL + Redis + MinIO.
  É produto empresarial, não biblioteca.
- **Memória**: nenhum projeto chegou a 1.0 em 2–3 anos de vida — Graphiti 0.29,
  Letta 0.16, Hindsight 0.8, sqlite-vec 0.1.x. **Kuzu** (banco de grafo embutido que
  o Graphiti oferecia) está **arquivado**. **OpenMemory** foi descontinuado e o nome
  foi **reciclado em outro produto**. `memobase` ficou 7 meses sem commit.
- Peso: `import cognee` arrasta FastAPI + gunicorn + fakeredis; Letta traz ~60
  dependências e Postgres; Mem0 exige Qdrant e embute telemetria.

A conclusão de uma das pesquisas resume: *não existe, em 2026, projeto de memória
que seja simultaneamente embutível como biblioteca leve, sem servidor externo, com
API estável e histórico que sustente dez anos. A dependência mais estável disponível
é o SQLite.*

## Consequências

Escrevemos ~600–800 linhas por subsistema (recuperação, memória) quando eles forem
necessários — código que entendemos inteiramente, sobre 5–6 dependências maduras de
propósito único. Em troca: sem comunidade, sem plugin de terceiro, e cada recurso
novo é código nosso.

**Copiar ideia é encorajado; importar dependência não.** Ideias que valem: extração
em duas fases do Mem0, bitemporalidade do Graphiti, playbook append-only do ACE,
blocos de memória com orçamento do Letta, reconciliação de total do `monopoly`.

## Gatilho de revisão

Reabrir quando um projeto desta categoria satisfizer **todos**: (a) 1.0 ou maior por
pelo menos 18 meses sem breaking change; (b) embutível sem processo externo; (c)
backend SQLite; (d) árvore de dependências que não inclua servidor web nem
telemetria. `Hindsight` (MIT, ativo) é o candidato a reavaliar em 2027.
