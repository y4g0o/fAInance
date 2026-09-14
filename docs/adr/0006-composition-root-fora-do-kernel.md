# ADR 0006 — Composition root fora do kernel

**Data:** 2026-08-05 · **Estado:** Aceita

## Contexto

O registro estático de módulos (`MODULOS`) morava em `nucleo/registro.py` e importava
`personalos.modulos.financas.modulo`. Ou seja: o kernel importava um módulo. Com um
módulo isso é invisível; com os treze previstos (saúde, estudos, projetos, livros,
hardware, carro, patrimônio, compras, agenda, documentos, automação, IA pessoal) o
kernel deixaria de ser reutilizável e o ciclo viraria um nó impossível de desatar.

## Decisão

`MODULOS` passa a viver em `personalos/composicao.py`, fora de `nucleo/`. O kernel
define o contrato (`Modulo`, `Vista`, `Insight`, `RegraInsight`) e **não importa
módulo nenhum**. Quem conhece todos os módulos é o composition root, que por
definição vive na borda.

## Consequências

`criar_engine` já recebia `metadatas` e `vistas` como parâmetro (a solução do ciclo
anterior); agora essa escolha fica coerente com o resto. O rename foi feito em commit
só-rename para preservar `git log --follow`.

A regra é **mecanizada**, não aspiracional: `test_kernel_nao_depende_de_nenhum_modulo`
varre `nucleo/` e falha o build se algum arquivo mencionar `personalos.modulos`.

## Gatilho de revisão

Nenhum previsto. Se algum dia o kernel precisar de discovery dinâmico de módulos
(hoje explicitamente recusado), o composition root é o único lugar que muda.
