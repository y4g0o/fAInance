"""Card do módulo financas para o Resumo Geral do painel.

A MESMA função serve dois consumidores — `GET /api/financas/resumo` e o campo
`Modulo.card` — para que painel e API não possam divergir.

Não formata nada por conta própria: valor sai de `Dinheiro.formatar()`, que é
testado, e o texto de "base: N meses" repete o que a CLI já diz.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from personalos.modulos.financas.aplicacao.analise import custo_basico_mensal
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.insights import gastos_fixos_conhecidos
from personalos.nucleo.modulo import CardResumo, Metrica

AVISO_SEM_DADOS = (
    "Nenhuma transação importada. Coloque extratos (OFX, CSV, XLSX ou PDF) em "
    "personalos/extratos/ e rode `personalos financas importar`."
)


def resumo(engine: Engine) -> CardResumo:
    with engine.connect() as conn:
        transacoes = conn.execute(
            text("SELECT count(*) FROM financas_transacoes")
        ).scalar_one()
        saldo = int(
            conn.execute(text("SELECT saldo_centavos FROM vw_financas_saldo_v1")).scalar() or 0
        )
    if not transacoes:
        return CardResumo(
            modulo="financas", titulo="Finanças", vazio=True, aviso=AVISO_SEM_DADOS
        )

    basico = custo_basico_mensal(engine)
    fixos = gastos_fixos_conhecidos(engine)
    metricas = [
        Metrica(
            rotulo="Saldo",
            valor=Dinheiro(saldo).formatar(),
            centavos=saldo,
            tom="alerta" if saldo < 0 else "neutro",
        )
    ]
    if basico.meses_considerados:
        metricas.append(
            Metrica(
                rotulo="Custo básico mensal",
                valor=Dinheiro(basico.total_centavos).formatar(),
                centavos=basico.total_centavos,
                detalhe=f"base: {basico.meses_considerados} mês(es) fechado(s)",
            )
        )
    else:
        metricas.append(
            Metrica(
                rotulo="Custo básico mensal",
                valor="—",
                detalhe="sem mês fechado ainda",
            )
        )
    metricas.append(
        Metrica(rotulo="Gastos fixos", valor=str(len(fixos)), centavos=None)
    )
    return CardResumo(modulo="financas", titulo="Finanças", metricas=tuple(metricas))
