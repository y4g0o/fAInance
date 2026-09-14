# Architecture Decision Records

Registro das decisões que são **caras de reverter**. O objetivo é que o
desenvolvedor de 2036 (provavelmente o mesmo de hoje) entenda *por que* o sistema
é assim, não só *como* ele é.

## Quando abrir um ADR

Abra quando a decisão envolver: banco de dados, formato de dado persistido,
protocolo entre camadas, dependência estrutural, ou uma regra que o código passa a
assumir em todo lugar. **Não** abra para escolha de nome, refatoração local, ou
biblioteca trocável em uma linha — para essas, docstring com o porquê basta.

Formato: contexto → decisão → consequências → **gatilho de revisão**. O gatilho é a
parte que mais envelhece bem: ele diz sob que evidência a decisão deve ser
reaberta, e evita tanto teimosia quanto reescrita por moda.

## Índice

| # | Decisão | Estado |
|---|---|---|
| [0001](0001-sqlite-como-banco-unico.md) | SQLite como banco único | Aceita |
| [0002](0002-llm-nunca-calcula.md) | A LLM nunca calcula | Aceita |
| [0003](0003-sem-framework-de-agente-nem-rag.md) | Sem framework de agente nem de RAG | Aceita |
| [0004](0004-convencao-de-sinal-nas-views.md) | Convenção de sinal nas views | Aceita |
| [0005](0005-sem-graphrag.md) | Sem GraphRAG | Aceita |
| [0006](0006-composition-root-fora-do-kernel.md) | Composition root fora do kernel | Aceita |
| [0007](0007-painel-sem-javascript.md) | Painel sem JavaScript (SVG no servidor) | Substituída pela 0008 |
| [0008](0008-spa-react-substitui-painel-sem-js.md) | SPA React substitui o painel sem JavaScript | Aceita |
| [0009](0009-escrita-http-e-verificacao-de-origem.md) | Escrita via HTTP e verificação de origem | Aceita |
