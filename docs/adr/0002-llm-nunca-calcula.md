# ADR 0002 — A LLM nunca calcula

**Data:** 2026-08-05 · **Estado:** Aceita

## Contexto

Este é um sistema financeiro. Um número errado apresentado com confiança é pior que
um erro visível: ele vira decisão de compra, de corte, de investimento. Modelos de
linguagem produzem números plausíveis e errados sem sinalizar. Durante o
desenvolvimento, o modelo local devolveu `.8990` para "89,90" — o parser leria
**R$ 0,90**, erro silencioso de 100×.

## Decisão

Todo número vem de função determinística testada. A LLM só **interpreta linguagem,
escolhe ferramenta e narra**. A regra é estrutural, não instrução de prompt.

## Os mecanismos que a tornam estrutural

1. **Ferramenta determinística como unidade.** Saldo, custo básico, juro embutido em
   parcelamento, projeção, detecção de gasto fixo: tudo em Python/SQL testado
   (`aplicacao/analise.py`, `aplicacao/consultas.py`, `insights.py`).
2. **Sinal derivado, não digitado.** Em `financas lancar` o valor é magnitude e o
   sinal vem de `--tipo`; erro de sinal do modelo é impossível por construção.
3. **Validação no schema.** `field_validator` recusa valor mal formado antes que
   chegue ao parser — foi o que matou o caso `.8990`.
4. **Narração sem dígitos** (fatia do consultor): o texto que o modelo produz não
   pode conter dígito nenhum; números entram por placeholder resolvido pelo código, e
   uma guarda rejeita dígito literal — **inclusive um número correto escrito à mão**.
   Audita-se o mecanismo, não o valor, e isso é testável.
5. **Fato sem citação não entra** (quando a memória existir):
   `CHECK (origem <> 'llm' OR citacao IS NOT NULL)` no schema, e valor monetário
   reconferido contra a fonte estruturada.

## Consequências

Não há streaming de tokens na resposta do consultor: os números só existem depois da
substituição. Em troca, toda resposta é auditável — dá para dizer qual função
produziu cada número. A guarda também rejeita dígito legítimo (mês "2026-08"), o que
exige placeholder para esses casos. Fricção aceita: o invariante absoluto é o que dá
a garantia.

## Gatilho de revisão

Nenhum. Esta decisão não se revisa por conveniência: ela é a razão de o sistema ser
confiável. Se um dia um modelo for aritmeticamente confiável, a arquitetura continua
correta — ferramenta determinística é mais rápida, mais barata e auditável.
