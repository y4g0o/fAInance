# ADR 0001 — SQLite como banco único

**Data:** 2026-08-05 · **Estado:** Aceita

## Contexto

O PersonalOS guarda finanças hoje e vai guardar saúde, estudos, projetos, livros,
patrimônio, documentos. Volume real de uma pessoa: ~50 mil transações e ~100 mil
chunks de documento em dez anos. Precisa rodar 100% local, sem serviço externo, e
ser mantido por uma pessoa por uma década. Considerados: SQLite, PostgreSQL +
pgvector, DuckDB ao lado, Redis, e bancos vetoriais dedicados (Qdrant, Chroma,
LanceDB, Milvus).

## Decisão

**Um arquivo SQLite**, com WAL, `synchronous=NORMAL`, FTS5 para busca lexical e —
quando houver documentos — vetores como BLOB em coluna própria, com `sqlite-vec`
como acelerador opcional e não como dependência crítica.

## Por quê

Um daemon a mais é dívida perpétua: em dez anos são dezenas de upgrades de major,
cada um com risco e ritual. Nenhuma outra tecnologia da stack tem compromisso de
estabilidade comparável — o projeto SQLite declara suporte e retrocompatibilidade
de formato **até 2050**. No volume-alvo, busca vetorial por força bruta em numpy
responde em dezenas de milissegundos, enquanto a geração do LLM local custa 8–15 s:
o índice vetorial otimizaria ~2% do tempo de resposta. Backup é `sqlite3 .backup` +
restic, que já funciona.

## Consequências

Aceitas: sem HNSW real (força bruta até ~2M vetores); um único processo escritor,
com escrita serializada (ver `nucleo/transacao.py`); sem MVCC.
Ganhas: zero processo para administrar, backup atômico de tudo junto, e a
atomicidade entre fato e vetor na mesma transação.

## Gatilho de revisão

Migrar para PostgreSQL + pgvector **somente** se um destes persistir por 30 dias:
(G1) dois escritores genuinamente concorrentes com **>5 `SQLITE_BUSY`/dia** após
`BEGIN IMMEDIATE` e `busy_timeout=15000`; (G2) p95 de busca vetorial **>300 ms** já
com vetor em int8 ou 256 dimensões; (G3) **>2.000.000** de vetores; (G4) **>500
transações de escrita/s** sustentadas; (G5) banco **>100 GB** ou backup levando
**>5 min**; (G6) segundo usuário com login próprio.

**Anti-gatilhos** — não migrar por "os dados cresceram", "quero pgvector", "quero
HNSW" ou "vou colocar num servidor". Ordem de escape antes do Postgres: reduzir
dimensão do vetor, quantizar, processo escritor único, e só então trocar de banco.

**DuckDB** entra apenas como leitor read-only para consulta ad-hoc, se alguma tabela
passar de ~2 milhões de linhas *e* as agregações passarem de ~1 s. Abaixo de 100 mil
linhas a diferença não é perceptível.
