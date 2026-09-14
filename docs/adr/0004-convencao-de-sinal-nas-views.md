# ADR 0004 — Convenção de sinal nas views

**Data:** 2026-08-05 · **Estado:** Aceita

## Contexto

As views analíticas nasceram com sinal inconsistente: despesa era negativa em
`vw_financas_despesas_v1` e `gastos_categoria`, e positiva em
`vw_financas_fluxo_mensal_v1.despesas_centavos`. Documentado, mas cada consumidor
novo (painel, gráfico, Metabase, agente) precisaria de uma tabela de exceções por
view. Além disso, `vw_financas_saldo_acumulado_v1` ignorava o saldo inicial das
contas, então um gráfico de evolução terminaria num valor diferente do saldo exibido.

## Decisão

O sinal depende do **tipo da coluna**, nunca da view:

1. `valor_centavos` é o valor do lançamento **com o sinal do ledger** (despesa
   negativa). É a coluna que reproduz o extrato.
2. Coluna agregada que mede despesa é **magnitude positiva** — plota direto, sem
   eixo invertido.
3. Coluna de valor líquido **mantém o sinal** (`saldo_centavos`,
   `resultado_centavos`, `saldo_acumulado_centavos`): negativo significa negativo.

Além disso, `vw_financas_saldo_acumulado_v1` parte do saldo inicial declarado, de
modo que a última linha **fecha** com `vw_financas_saldo_v1`.

## Consequências

As views `_v1` foram emendadas em vez de virarem `_v2`, porque o único consumidor
publicado era a CLI. A função Python equivalente (`consultas.gastos_por_categoria`)
segue a mesma regra e a mesma ordem, e o teste de paridade passou a comparar lista
ordenada em vez de dicionário — drift entre SQL e Python vira build vermelho.

## Gatilho de revisão

Mudar a lógica de uma view já consumida por algo fora deste repositório (Metabase
salvo, script do usuário) exige criar `_v2` e manter `_v1` até a migração — é o
propósito do sufixo de versão.
