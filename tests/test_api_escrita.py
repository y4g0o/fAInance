"""Endpoints de escrita: HTTP adaptando casos de uso, sem regra própria.

Dados sintéticos em tmp_path — nenhum teste toca o banco real.
"""
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from .apoio import cliente_navegador

from personalos.api.app import criar_app
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoTransacoesSQL

ORFAS = [
    Transacao("i1", date(2026, 6, 3), Dinheiro(-3290), "PIX QRS DELIVERIA BR", "conta"),
    Transacao("i2", date(2026, 6, 9), Dinheiro(-1850), "PIX QRS DELIVERIA BR", "conta"),
    Transacao("c1", date(2026, 6, 10), Dinheiro(-5611), "PIX QRS TELECOMIX", "conta"),
]


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    app = criar_app(db=tmp_path / "escrita.db")
    RepoTransacoesSQL(app.state.engine).inserir_muitas(ORFAS)
    return cliente_navegador(app)


def test_lancamento_manual_grava_com_sinal_negativo(cliente):
    r = cliente.post(
        "/api/financas/lancamentos",
        json={"descricao": "cafe", "valor": "7,50", "tipo": "despesa", "data": "2026-09-14"},
    )

    assert r.status_code == 201
    assert r.json()["valor_centavos"] == -750


def test_lancamento_com_tipo_invalido_da_422_explicando(cliente):
    r = cliente.post(
        "/api/financas/lancamentos",
        json={"descricao": "cafe", "valor": "7,50", "tipo": "saida"},
    )

    assert r.status_code == 422
    assert "tipo" in r.json()["detail"]


def test_categorizar_em_lote_devolve_os_fit_ids_alterados(cliente):
    """O desfazer da tela depende dessa lista — sem ela seria adivinhação."""
    r = cliente.post(
        "/api/financas/transacoes/categorizar-em-lote",
        json={"padrao": "deliveria", "categoria": "Delivery", "criar_regra": True},
    )

    assert r.status_code == 200
    corpo = r.json()
    assert sorted(corpo["fit_ids"]) == ["i1", "i2"]
    assert corpo["regra_criada"] is True


def test_saldo_inicial_da_conta_aceita_texto_brasileiro(cliente):
    r = cliente.put("/api/financas/contas/itau", json={"saldo_inicial": "1.234,56"})

    assert r.status_code == 200
    assert r.json()["saldo_inicial_centavos"] == 123456


def test_categoria_de_transacao_inexistente_da_404_falando_dela(cliente):
    """Afirmar só o 404 daria verde com a rota inexistente — o detalhe precisa
    dizer que foi a TRANSAÇÃO que não existe, senão o teste não prova nada."""
    r = cliente.patch("/api/financas/transacoes/nao-existe", json={"categoria": "X"})

    assert r.status_code == 404
    assert "nao-existe" in r.json()["detail"]


def test_categoria_de_transacao_existente_muda_o_banco(cliente):
    r = cliente.patch("/api/financas/transacoes/c1", json={"categoria": "Telefonia"})

    assert r.status_code == 200
    conferida = cliente.get("/api/financas/gastos?limite=50").json()
    assert [t for t in conferida if t["fit_id"] == "c1"][0]["categoria"] == "Telefonia"


def test_paridade_lancamento_api_e_cli_produzem_o_mesmo_estado(tmp_path):
    """A regra central da spec, mecanizada: a mesma operação pelos dois caminhos
    tem que produzir estado idêntico. Passa desde o primeiro dia porque ambos
    chamam a mesma função — e é justamente isso que este teste protege: se
    alguém reimplementar a lógica num endpoint, ele fica vermelho.
    """
    from typer.testing import CliRunner

    from personalos.cli import app as cli_app

    db_api = tmp_path / "via_api.db"
    db_cli = tmp_path / "via_cli.db"

    api = cliente_navegador(criar_app(db=db_api))
    api.post(
        "/api/financas/lancamentos",
        json={"descricao": "cafe", "valor": "7,50", "tipo": "despesa", "data": "2026-09-14"},
    )

    CliRunner().invoke(
        cli_app,
        ["financas", "lancar", "cafe", "7,50", "--data", "2026-09-14", "--db", str(db_cli)],
    )

    def estado(db):
        cliente = cliente_navegador(criar_app(db=db))
        return [
            (t["fit_id"], t["valor_centavos"], t["descricao"], t["categoria"])
            for t in cliente.get("/api/financas/gastos?limite=50").json()
        ]

    assert estado(db_api) == estado(db_cli)


def test_desfazer_lote_pela_api_volta_tudo(cliente):
    """O ciclo que a tela faz: aplicar, e desfazer se o usuário se arrepender."""
    aplicado = cliente.post(
        "/api/financas/transacoes/categorizar-em-lote",
        json={"padrao": "deliveria", "categoria": "Delivery", "criar_regra": True},
    ).json()

    r = cliente.post(
        "/api/financas/transacoes/desfazer-lote",
        json={"fit_ids": aplicado["fit_ids"], "padrao_da_regra": "deliveria"},
    )

    assert r.status_code == 200
    assert r.json()["voltaram"] == 2
    gastos = cliente.get("/api/financas/gastos?limite=50").json()
    assert all(t["categoria"] is None for t in gastos if t["fit_id"].startswith("i"))
