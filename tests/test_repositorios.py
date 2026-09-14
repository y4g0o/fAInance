from datetime import date

import pytest

from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Regra, Transacao
from personalos.modulos.financas.infra.repositorios import RepoContasSQL


def _t(fit_id: str, dia: int, cents: int, cat=None) -> Transacao:
    return Transacao(fit_id, date(2026, 6, dia), Dinheiro(cents), "compra", "nubank", cat)


def test_inserir_e_listar(repo_transacoes):
    n = repo_transacoes.inserir_muitas([_t("a", 1, -1000), _t("b", 2, -2000)])
    assert n == 2
    assert len(repo_transacoes.listar()) == 2


def test_dedup_por_fit_id(repo_transacoes):
    repo_transacoes.inserir_muitas([_t("a", 1, -1000)])
    n = repo_transacoes.inserir_muitas([_t("a", 1, -1000), _t("c", 3, -500)])
    assert n == 1  # "a" ignorado
    assert len(repo_transacoes.listar()) == 2


def test_dedup_dentro_do_mesmo_lote(repo_transacoes):
    n = repo_transacoes.inserir_muitas([_t("dup", 1, -100), _t("dup", 1, -100), _t("x", 2, -200)])
    assert n == 2
    assert len(repo_transacoes.listar()) == 2


def test_listar_por_periodo(repo_transacoes):
    repo_transacoes.inserir_muitas([_t("a", 1, -1000), _t("b", 20, -2000)])
    r = repo_transacoes.listar(inicio=date(2026, 6, 10), fim=date(2026, 6, 30))
    assert [t.fit_id for t in r] == ["b"]


def test_regras_crud(repo_regras):
    repo_regras.adicionar(Regra("uber", "Transporte"))
    assert [r.categoria for r in repo_regras.listar()] == ["Transporte"]


def test_definir_saldo_inicial_e_listar(engine):
    repo = RepoContasSQL(engine)
    repo.definir_saldo_inicial("nubank", Dinheiro(50000))
    assert repo.listar() == [("nubank", Dinheiro(50000))]


def test_definir_saldo_inicial_sobrescreve(engine):
    repo = RepoContasSQL(engine)
    repo.definir_saldo_inicial("nubank", Dinheiro(50000))
    repo.definir_saldo_inicial("nubank", Dinheiro(70000))
    assert repo.listar() == [("nubank", Dinheiro(70000))]


def test_listar_multiplas_contas(engine):
    repo = RepoContasSQL(engine)
    repo.definir_saldo_inicial("nubank", Dinheiro(50000))
    repo.definir_saldo_inicial("itau", Dinheiro(-1000))
    assert set(repo.listar()) == {("nubank", Dinheiro(50000)), ("itau", Dinheiro(-1000))}


def test_definir_saldo_inicial_nome_vazio_gera_erro(engine):
    repo = RepoContasSQL(engine)
    with pytest.raises(ValueError):
        repo.definir_saldo_inicial("", Dinheiro(100))


def test_definir_saldo_inicial_nome_so_espacos_gera_erro(engine):
    repo = RepoContasSQL(engine)
    with pytest.raises(ValueError):
        repo.definir_saldo_inicial("   ", Dinheiro(100))
