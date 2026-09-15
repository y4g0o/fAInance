"""Consultas determinísticas sobre transações. Toda 'matemática' vive aqui."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Engine

from personalos.modulos.financas.aplicacao.portas import RepoTransacoes
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import e_consumo
from personalos.modulos.financas.dominio.modelos import Transacao


def saldo(
    repo: RepoTransacoes, inicio: date | None = None, fim: date | None = None
) -> Dinheiro:
    """Soma só as transações — não inclui saldo inicial de conta.
    Fonte de verdade pro saldo total real é vw_financas_saldo_v1 (usada pela CLI)."""
    total = Dinheiro(0)
    for t in repo.listar(inicio, fim):
        total = total + t.valor
    return total


def maiores_gastos(
    repo: RepoTransacoes,
    limite: int = 10,
    inicio: date | None = None,
    fim: date | None = None,
) -> list[Transacao]:
    saidas = [t for t in repo.listar(inicio, fim) if t.valor.centavos < 0]
    return sorted(saidas, key=lambda t: t.valor.centavos)[:limite]


def gastos_por_categoria(
    repo: RepoTransacoes,
    inicio: date | None = None,
    fim: date | None = None,
    nao_consumo: Collection[str] = (),
) -> list[tuple[str, Dinheiro]]:
    """Total GASTO por categoria como magnitude positiva, maior primeiro (empate
    resolvido pelo nome). Mesma convenção de sinal e mesma ordem de
    vw_financas_gastos_categoria_v1 — ver docstring de analytics/vistas.py.

    Movimentação não entra: investimento e transferência entre contas próprias
    saem do extrato sem serem consumidas. Sem este filtro o gráfico de gasto
    discordava do ranking de cortes, que já respeitava a regra — e duas telas
    discordando é pior que uma errada, porque ninguém sabe em qual acreditar.
    """
    acc: dict[str, Dinheiro] = defaultdict(lambda: Dinheiro(0))
    for t in repo.listar(inicio, fim):
        if t.valor.centavos >= 0 or not e_consumo(t.categoria, nao_consumo):
            continue
        chave = t.categoria or "Sem categoria"
        acc[chave] = acc[chave] - t.valor
    return sorted(acc.items(), key=lambda kv: (-kv[1].centavos, kv[0]))


def fluxo_mensal(engine: Engine) -> list[dict[str, object]]:
    """View-first: lê vw_financas_fluxo_mensal_v1 direto, sem duplicar a agregação em Python."""
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(text("SELECT * FROM vw_financas_fluxo_mensal_v1")).mappings()
        ]
