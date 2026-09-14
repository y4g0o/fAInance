from datetime import date
from pathlib import Path

from sqlalchemy import text

from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.aplicacao import consultas
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoContasSQL, RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo.db import criar_engine


def _semear(tmp_path: Path):
    engine = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    repo_tx = RepoTransacoesSQL(engine)
    repo_tx.inserir_muitas(
        [
            Transacao("a", date(2026, 6, 1), Dinheiro(300000), "salario", "nubank"),
            Transacao("b", date(2026, 6, 2), Dinheiro(-99900), "mercado", "nubank", "Alimentação"),
            Transacao("c", date(2026, 6, 3), Dinheiro(-1234), "uber", "nubank", "Transporte"),
            Transacao("d", date(2026, 6, 4), Dinheiro(-500), "cafe", "nubank"),
        ]
    )
    return engine, repo_tx


def test_paridade_saldo_sem_conta_declarada(tmp_path):
    engine, repo_tx = _semear(tmp_path)
    esperado = consultas.saldo(repo_tx).centavos
    with engine.connect() as conn:
        real = conn.execute(text("SELECT saldo_centavos FROM vw_financas_saldo_v1")).scalar()
    assert real == esperado


def test_paridade_saldo_com_saldo_inicial(tmp_path):
    engine, repo_tx = _semear(tmp_path)
    RepoContasSQL(engine).definir_saldo_inicial("nubank", Dinheiro(50000))
    with engine.connect() as conn:
        real = conn.execute(text("SELECT saldo_centavos FROM vw_financas_saldo_v1")).scalar()
    assert real == consultas.saldo(repo_tx).centavos + 50000


def test_paridade_gastos_por_categoria(tmp_path):
    engine, repo_tx = _semear(tmp_path)
    # Lista ORDENADA (não dict): a view e a função Python compartilham a mesma
    # convenção de sinal e a mesma ordenação, então a paridade cobre as duas.
    esperado = [(nome, d.centavos) for nome, d in consultas.gastos_por_categoria(repo_tx)]
    with engine.connect() as conn:
        real = [
            (row["categoria"], row["total_centavos"])
            for row in conn.execute(text("SELECT * FROM vw_financas_gastos_categoria_v1")).mappings()
        ]
    assert real == esperado
    assert all(total > 0 for _, total in real), "despesa agregada é magnitude positiva"


def test_paridade_maiores_gastos(tmp_path):
    engine, repo_tx = _semear(tmp_path)
    esperado = [(t.fit_id, t.valor.centavos) for t in consultas.maiores_gastos(repo_tx, limite=10)]
    with engine.connect() as conn:
        real = [
            (row["fit_id"], row["valor_centavos"])
            for row in conn.execute(
                text("SELECT * FROM vw_financas_maiores_gastos_v1 LIMIT 10")
            ).mappings()
        ]
    assert real == esperado


def test_vw_financas_receitas_retorna_apenas_entradas(tmp_path):
    engine, repo_tx = _semear(tmp_path)
    with engine.connect() as conn:
        linhas = list(conn.execute(text("SELECT * FROM vw_financas_receitas_v1")).mappings())
    assert [row["fit_id"] for row in linhas] == ["a"]
    assert linhas[0]["valor_centavos"] == 300000


def test_vw_financas_despesas_retorna_apenas_saidas_em_ordem(tmp_path):
    engine, repo_tx = _semear(tmp_path)
    with engine.connect() as conn:
        linhas = list(conn.execute(text("SELECT * FROM vw_financas_despesas_v1")).mappings())
    assert [row["fit_id"] for row in linhas] == ["b", "c", "d"]
    assert all(row["valor_centavos"] < 0 for row in linhas)


def test_vw_financas_saldo_acumulado_e_cumulativo_em_ordem(tmp_path):
    engine, repo_tx = _semear(tmp_path)
    with engine.connect() as conn:
        linhas = list(
            conn.execute(text("SELECT * FROM vw_financas_saldo_acumulado_v1")).mappings()
        )
    assert [row["fit_id"] for row in linhas] == ["a", "b", "c", "d"]
    assert [row["saldo_acumulado_centavos"] for row in linhas] == [
        300000,
        300000 - 99900,
        300000 - 99900 - 1234,
        300000 - 99900 - 1234 - 500,
    ]


def test_saldo_acumulado_parte_do_saldo_inicial_e_fecha_com_vw_saldo(tmp_path):
    # A última linha do acumulado tem que ser o saldo total. Sem incluir o saldo
    # inicial das contas, um gráfico de evolução terminaria num valor diferente
    # do saldo exibido — inconsistência visível pra quem olha as duas coisas.
    engine, _ = _semear(tmp_path)
    RepoContasSQL(engine).definir_saldo_inicial("nubank", Dinheiro(50000))
    with engine.connect() as conn:
        linhas = list(
            conn.execute(text("SELECT * FROM vw_financas_saldo_acumulado_v1")).mappings()
        )
        saldo_total = conn.execute(
            text("SELECT saldo_centavos FROM vw_financas_saldo_v1")
        ).scalar()
    assert linhas[0]["saldo_acumulado_centavos"] == 50000 + 300000
    assert linhas[-1]["saldo_acumulado_centavos"] == saldo_total


def test_vw_financas_receitas_ordena_por_data_e_fit_id_em_empate_de_data(tmp_path):
    # Duas receitas na MESMA data — sem tiebreak por fit_id no ORDER BY, a
    # ordem ficaria dependente da ordem física de inserção. Insere fora de
    # ordem alfabética de propósito (z1 antes de a1).
    engine = criar_engine(tmp_path / "empate_receitas.db", metadatas=(metadata_financas,), vistas=VISTAS)
    repo_tx = RepoTransacoesSQL(engine)
    repo_tx.inserir_muitas(
        [
            Transacao("z1", date(2026, 6, 1), Dinheiro(1000), "receita z", "nubank"),
            Transacao("a1", date(2026, 6, 1), Dinheiro(2000), "receita a", "nubank"),
        ]
    )
    with engine.connect() as conn:
        linhas = list(conn.execute(text("SELECT * FROM vw_financas_receitas_v1")).mappings())
    assert [row["fit_id"] for row in linhas] == ["a1", "z1"]


def test_vw_financas_despesas_ordena_por_data_e_fit_id_em_empate_de_data(tmp_path):
    # Mesma lógica acima, para despesas.
    engine = criar_engine(tmp_path / "empate_despesas.db", metadatas=(metadata_financas,), vistas=VISTAS)
    repo_tx = RepoTransacoesSQL(engine)
    repo_tx.inserir_muitas(
        [
            Transacao("z1", date(2026, 6, 1), Dinheiro(-1000), "despesa z", "nubank"),
            Transacao("a1", date(2026, 6, 1), Dinheiro(-2000), "despesa a", "nubank"),
        ]
    )
    with engine.connect() as conn:
        linhas = list(conn.execute(text("SELECT * FROM vw_financas_despesas_v1")).mappings())
    assert [row["fit_id"] for row in linhas] == ["a1", "z1"]


def test_vw_financas_saldo_acumulado_calcula_linha_a_linha_em_empate_de_data(tmp_path):
    # Duas transações na MESMA data: A=-200 (fit_id="a1") e B=+100 (fit_id="z1").
    # Insere fora de ordem alfabética (z1 antes de a1) para não depender da
    # ordem física de inserção. Se a window function tratasse as duas linhas
    # empatadas em "data" como um único peer group (bug clássico de RANGE em
    # vez de ROWS), o saldo acumulado apareceria como -100 nas DUAS linhas,
    # em vez de -200 depois -100.
    engine = criar_engine(tmp_path / "empate_saldo.db", metadatas=(metadata_financas,), vistas=VISTAS)
    repo_tx = RepoTransacoesSQL(engine)
    repo_tx.inserir_muitas(
        [
            Transacao("z1", date(2026, 6, 1), Dinheiro(100), "b", "nubank"),
            Transacao("a1", date(2026, 6, 1), Dinheiro(-200), "a", "nubank"),
        ]
    )
    with engine.connect() as conn:
        linhas = list(
            conn.execute(text("SELECT * FROM vw_financas_saldo_acumulado_v1")).mappings()
        )
    assert [row["fit_id"] for row in linhas] == ["a1", "z1"]
    assert [row["saldo_acumulado_centavos"] for row in linhas] == [-200, -100]


def test_paridade_maiores_gastos_com_empate_na_fronteira_do_limite(tmp_path):
    # 12 transações empatadas no mesmo valor e na mesma data — sem um tiebreak
    # determinístico (fit_id), a ordem de quem entra nos primeiros 10 fica
    # dependente da ordem física das linhas em cada lado (SQLite vs. Python),
    # podendo divergir. Insere fora de ordem alfabética de propósito.
    engine = criar_engine(tmp_path / "empate.db", metadatas=(metadata_financas,), vistas=VISTAS)
    repo_tx = RepoTransacoesSQL(engine)
    fit_ids_fora_de_ordem = ["g", "c", "k", "a", "j", "e", "l", "b", "i", "f", "h", "d"]
    repo_tx.inserir_muitas(
        [
            Transacao(fit_id, date(2026, 6, 1), Dinheiro(-90000), "gasto empatado", "nubank")
            for fit_id in fit_ids_fora_de_ordem
        ]
    )
    esperado = [t.fit_id for t in consultas.maiores_gastos(repo_tx, limite=10)]
    with engine.connect() as conn:
        real = [
            row["fit_id"]
            for row in conn.execute(
                text("SELECT * FROM vw_financas_maiores_gastos_v1 LIMIT 10")
            ).mappings()
        ]
    assert real == esperado
    assert esperado == list("abcdefghij")
