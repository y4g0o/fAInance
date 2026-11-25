"""`personalos financas demo`: dados sintéticos para conhecer a interface."""
from datetime import date
from pathlib import Path

from sqlalchemy import text
from typer.testing import CliRunner

from personalos.modulos.financas import insights as insights_financas
from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.aplicacao import sugestoes
from personalos.modulos.financas.cli import app
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo import insights as motor_insights
from personalos.nucleo.db import criar_engine

runner = CliRunner()


def _engine(db: Path):
    return criar_engine(db, metadatas=(metadata_financas,), vistas=VISTAS)


def test_demo_carrega_meses_de_transacoes_num_banco_vazio(tmp_path):
    db = tmp_path / "demo.db"
    resultado = runner.invoke(app, ["demo", "--db", str(db)])
    assert resultado.exit_code == 0, resultado.stdout
    assert "transações" in resultado.stdout

    with _engine(db).connect() as conn:
        meses = conn.execute(
            text("SELECT COUNT(DISTINCT strftime('%Y-%m', data)) FROM financas_transacoes")
        ).scalar_one()
        futuras = conn.execute(
            text("SELECT COUNT(*) FROM financas_transacoes WHERE data > :hoje"),
            {"hoje": date.today().isoformat()},
        ).scalar_one()
        saldo = conn.execute(text("SELECT saldo_centavos FROM vw_financas_saldo_v1")).scalar_one()
    assert 3 <= meses <= 6
    assert futuras == 0
    assert saldo > 0  # conta declarada: a tela não abre com R$ 0,00


def test_demo_tem_fixos_nao_categorizadas_e_anomalia(tmp_path):
    db = tmp_path / "demo.db"
    assert runner.invoke(app, ["demo", "--db", str(db)]).exit_code == 0
    engine = _engine(db)

    fixos = {f.chave for f in insights_financas.gastos_fixos_conhecidos(engine)}
    assert {"aluguel", "internet fibra", "streaming filmes"} <= fixos
    assert "supermercado bom preco" not in fixos  # recorrente, mas de valor variável

    assert len(sugestoes.sugerir_regras(engine, 10, 2)) >= 2

    regras = {i.regra_id for i in motor_insights.listar(engine, status=None)}
    assert "financas_categoria_acima_da_media" in regras


def test_demo_recusa_banco_com_transacoes(tmp_path):
    db = tmp_path / "meu.db"
    RepoTransacoesSQL(_engine(db)).inserir_muitas(
        [Transacao("x", date(2026, 1, 5), Dinheiro(-1000), "compra minha", "nubank")]
    )
    resultado = runner.invoke(app, ["demo", "--db", str(db)])
    assert resultado.exit_code == 1
    assert "já tem" in resultado.stdout
    with _engine(db).connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM financas_transacoes")).scalar_one()
    assert total == 1
