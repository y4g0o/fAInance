"""Saldo só existe para conta com ponto de partida declarado.

Ao importar a segunda conta, o saldo passou a somar o movimento dela — mas ela
nunca teve saldo inicial informado. O resultado era "saldo da primeira conta
mais o líquido da segunda", que não é saldo de nada.

É o mesmo princípio de sempre: sem dado é sem dado. Movimento não vira saldo por
falta de alternativa.
"""
from datetime import date
from pathlib import Path

import pytest

from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoContasSQL, RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo.db import criar_engine
from sqlalchemy import text


@pytest.fixture
def engine(tmp_path: Path):
    e = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    RepoTransacoesSQL(e).inserir_muitas(
        [
            Transacao("i1", date(2026, 6, 1), Dinheiro(-10000), "GASTO ITAU", "itau"),
            Transacao("n1", date(2026, 6, 2), Dinheiro(50000), "PRESENTE", "nubank"),
            Transacao("n2", date(2026, 6, 3), Dinheiro(-20000), "GASTO NUBANK", "nubank"),
        ]
    )
    RepoContasSQL(e).definir_saldo_inicial("itau", Dinheiro(100000))
    return e


def _saldo(engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT saldo_centavos FROM vw_financas_saldo_v1")).scalar_one())


def test_saldo_ignora_conta_sem_saldo_inicial_declarado(engine):
    """R$ 1.000 de saldo inicial menos R$ 100 de gasto = R$ 900. O movimento do
    Nubank (+500 −200) não entra: sem ponto de partida, ele não descreve saldo."""
    assert _saldo(engine) == 90000


def test_declarar_a_segunda_conta_a_traz_para_o_saldo(engine):
    """Quando o usuário informa o ponto de partida, a conta passa a contar."""
    RepoContasSQL(engine).definir_saldo_inicial("nubank", Dinheiro(0))

    assert _saldo(engine) == 90000 + 50000 - 20000
