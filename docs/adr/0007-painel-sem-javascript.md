# ADR 0007 — Painel sem JavaScript (SVG no servidor, formulário HTML)

**Data:** 2026-08-06 · **Estado:** Aceita · **Substitui:** decisão de Chart.js + HTMX
da spec do v0.2

## Contexto

A spec do v0.2 decidiu painel com **HTMX** (interação sem recarregar) e **Chart.js**
(gráficos), ambos vendorizados. O argumento era evitar toolchain JS mantendo
interatividade. Ao implementar, ficou registrado um gatilho: *"se ao fim do v0.2.3 o
painel tiver ≤2 gráficos simples, avaliar SVG server-rendered e remover Chart.js"*.

O painel terminou com **um** gráfico (barras de fluxo mensal) e **uma** interação
(dispensar insight). O gatilho está satisfeito.

## Decisão

**Zero JavaScript.** Gráfico em SVG gerado no servidor (~60 linhas, função pura) e
interação por formulário HTML com POST/Redirect/GET.

## Por quê

- **Custo real do que foi evitado:** ~200 KB de Chart.js + ~14 KB de HTMX
  versionados no git, mais um `VENDOR.md` com versão, URL, SHA-256 e licença para
  manter por dez anos, mais dois projetos para acompanhar.
- **Benefício real perdido:** tooltip nativo (substituído por `<title>` no SVG, que o
  navegador mostra no hover) e evitar um reload de página. Num servidor local o
  reload é imperceptível.
- **Ganhos:** funciona com JavaScript desligado; o gráfico é **função pura testável**
  (há teste conferindo que a barra do dobro do valor tem o dobro da altura, e que
  conteúdo do extrato é escapado); nenhum asset para envelhecer; nada para auditar
  quando surgir CVE em biblioteca de front.
- **Coerência com a carta:** "zero toolchain para sobreviver dez anos" é incompatível
  com vendorizar 200 KB de JavaScript para desenhar retângulos.

## Consequências

- Toda interação recarrega a página. Aceito: é um painel local de um usuário.
- Gráfico mais rico (zoom, séries dinâmicas, tooltip customizado) exigiria mudança
  de abordagem, não incremento.
- `python-multipart` também foi evitado: `Form()` **e** `request.form()` exigem essa
  dependência nesta versão do Starlette (verificado — o assert vem antes de olhar o
  content-type), e um formulário de um campo é urlencoded, que `urllib.parse.parse_qs`
  resolve em uma linha.

## Gatilho de revisão

Adotar HTMX quando houver **interação que o reload torne desconfortável de verdade**
— edição inline, lista longa com filtro incremental, ou atualização parcial
frequente. Adotar biblioteca de gráfico quando um gráfico exigir zoom, seleção de
período interativa, ou mais de três séries sobrepostas. Em ambos os casos: dor
documentada, não antecipação.
