from datetime import date
from pathlib import Path

from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.aplicacao.consultas import (
    fluxo_mensal,
    gastos_por_categoria,
    maiores_gastos,
    saldo,
)
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo.db import criar_engine


def _t(fit, dia, cents, cat=None, desc="x"):
    return Transacao(fit, date(2026, 6, dia), Dinheiro(cents), desc, "nubank", cat)


def _repo(monkeypatch, transacoes):
    class R:
        def listar(self, inicio=None, fim=None):
            return [
                t for t in transacoes
                if (inicio is None or t.data >= inicio)
                and (fim is None or t.data <= fim)
            ]
    return R()


def test_saldo(monkeypatch):
    repo = _repo(monkeypatch, [_t("a", 1, 300000), _t("b", 2, -99900)])
    assert saldo(repo).centavos == 200100


def test_maiores_gastos_ordena_por_valor(monkeypatch):
    repo = _repo(monkeypatch, [_t("a", 1, -1000, desc="p"), _t("b", 2, -5000, desc="q"),
                               _t("c", 3, 3000, desc="entrada")])
    top = maiores_gastos(repo, limite=2)
    assert [t.descricao for t in top] == ["q", "p"]  # só saídas, maior primeiro


def test_gastos_por_categoria(monkeypatch):
    repo = _repo(monkeypatch, [_t("a", 1, -1000, cat="Transporte"),
                               _t("b", 2, -2000, cat="Transporte"),
                               _t("c", 3, -500, cat=None)])
    # Magnitude positiva, maior gasto primeiro (convenção única — vistas.py).
    resultado = gastos_por_categoria(repo)
    assert resultado == [("Transporte", Dinheiro(3000)), ("Sem categoria", Dinheiro(500))]


def test_fluxo_mensal(tmp_path: Path):
    engine = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    RepoTransacoesSQL(engine).inserir_muitas(
        [
            Transacao("a", date(2026, 6, 1), Dinheiro(300000), "salario", "nubank"),
            Transacao("b", date(2026, 6, 2), Dinheiro(-99900), "mercado", "nubank"),
            Transacao("c", date(2026, 7, 1), Dinheiro(50000), "salario", "nubank"),
            Transacao("d", date(2026, 7, 2), Dinheiro(-20000), "aluguel", "nubank"),
        ]
    )
    linhas = {row["mes"]: row for row in fluxo_mensal(engine)}
    assert linhas["2026-06"]["receitas_centavos"] == 300000
    assert linhas["2026-06"]["despesas_centavos"] == 99900
    assert linhas["2026-06"]["resultado_centavos"] == 200100
    assert linhas["2026-07"]["receitas_centavos"] == 50000
    assert linhas["2026-07"]["despesas_centavos"] == 20000
    assert linhas["2026-07"]["resultado_centavos"] == 30000
