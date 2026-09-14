from datetime import date

from personalos.modulos.financas.dominio.categorizador import categorizar
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Regra, Transacao


def _t(descricao: str) -> Transacao:
    return Transacao("id1", date(2026, 6, 1), Dinheiro(-1000), descricao, "nubank")


def test_contem_case_insensitive():
    regras = [Regra("uber", "Transporte")]
    assert categorizar(_t("UBER *TRIP 123"), regras) == "Transporte"


def test_regex():
    regras = [Regra(r"^deliveria", "Alimentação", tipo="regex")]
    assert categorizar(_t("Deliveria pedido"), regras) == "Alimentação"


def test_prioridade_menor_vence():
    regras = [
        Regra("mercado", "Compras", prioridade=100),
        Regra("mercado livre", "Compras Online", prioridade=10),
    ]
    assert categorizar(_t("MERCADO LIVRE"), regras) == "Compras Online"


def test_sem_match_retorna_none():
    assert categorizar(_t("xyz"), [Regra("uber", "Transporte")]) is None
