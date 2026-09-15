"""Views SQL do módulo financas — contrato de leitura estável pro painel/Metabase.

Sempre expõem *_centavos (nunca float). Sufixo _v1: mudar a lógica de uma view
publicada cria _v2 mantendo _v1 até os consumidores migrarem (ver design doc).

Convenção de sinal — regra ÚNICA, vale pra toda view (e pras funções
equivalentes em aplicacao/consultas.py):

1. `valor_centavos` é o valor do lançamento COM o sinal do ledger — despesa
   negativa, receita positiva (vw_financas_maiores_gastos_v1, _receitas_v1,
   _despesas_v1). É a coluna que reproduz o extrato.
2. Coluna agregada que mede despesa é MAGNITUDE POSITIVA
   (vw_financas_gastos_categoria_v1.total_centavos,
   vw_financas_fluxo_mensal_v1.despesas_centavos) — plota direto, sem eixo
   invertido.
3. Coluna de valor líquido mantém o sinal (saldo_centavos,
   resultado_centavos, saldo_acumulado_centavos) — negativo significa negativo
   de verdade.

O sinal depende do TIPO da coluna, nunca da view: um consumidor não precisa de
tabela de exceções por view.

vw_financas_saldo_acumulado_v1 parte do saldo inicial declarado das contas, de
modo que a última linha fecha com vw_financas_saldo_v1."""
from __future__ import annotations

from personalos.nucleo.modulo import Vista

VISTAS: tuple[Vista, ...] = (
    Vista(
        "vw_financas_saldo_v1",
        """
        SELECT
            (SELECT COALESCE(SUM(valor_centavos), 0) FROM financas_transacoes
                WHERE conta IN (SELECT nome FROM financas_contas)) +
            (SELECT COALESCE(SUM(saldo_inicial_centavos), 0) FROM financas_contas)
            AS saldo_centavos
        """,
    ),
    Vista(
        "vw_financas_gastos_categoria_v1",
        """
        SELECT
            COALESCE(categoria, 'Sem categoria') AS categoria,
            SUM(-valor_centavos) AS total_centavos
        FROM financas_transacoes
        WHERE valor_centavos < 0
        GROUP BY COALESCE(categoria, 'Sem categoria')
        ORDER BY total_centavos DESC, categoria ASC
        """,
    ),
    Vista(
        "vw_financas_maiores_gastos_v1",
        """
        SELECT fit_id, data, valor_centavos, descricao, conta, categoria
        FROM financas_transacoes
        WHERE valor_centavos < 0
        ORDER BY valor_centavos ASC, data ASC, fit_id ASC
        """,
    ),
    Vista(
        "vw_financas_fluxo_mensal_v1",
        """
        SELECT
            strftime('%Y-%m', data) AS mes,
            SUM(CASE WHEN valor_centavos > 0 THEN valor_centavos ELSE 0 END) AS receitas_centavos,
            SUM(CASE WHEN valor_centavos < 0 THEN -valor_centavos ELSE 0 END) AS despesas_centavos,
            SUM(valor_centavos) AS resultado_centavos
        FROM financas_transacoes
        GROUP BY mes
        ORDER BY mes
        """,
    ),
    Vista(
        "vw_financas_receitas_v1",
        """
        SELECT fit_id, data, valor_centavos, descricao, conta, categoria
        FROM financas_transacoes
        WHERE valor_centavos > 0
        ORDER BY data, fit_id
        """,
    ),
    Vista(
        "vw_financas_despesas_v1",
        """
        SELECT fit_id, data, valor_centavos, descricao, conta, categoria
        FROM financas_transacoes
        WHERE valor_centavos < 0
        ORDER BY data, fit_id
        """,
    ),
    Vista(
        "vw_financas_saldo_acumulado_v1",
        """
        SELECT
            data,
            fit_id,
            (SELECT COALESCE(SUM(saldo_inicial_centavos), 0) FROM financas_contas)
            + SUM(valor_centavos) OVER (ORDER BY data, fit_id)
            AS saldo_acumulado_centavos
        FROM financas_transacoes
        ORDER BY data, fit_id
        """,
    ),
)
