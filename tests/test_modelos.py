import pytest

from personalos.modulos.financas.dominio.modelos import Regra


def test_regra_valida_constroi():
    regra = Regra("uber", "Transporte")
    assert regra.padrao == "uber"
    assert regra.categoria == "Transporte"
    assert regra.tipo == "contem"
    assert regra.prioridade == 100


def test_tipo_invalido_levanta_erro():
    with pytest.raises(ValueError):
        Regra("uber", "Transporte", tipo="invalido")


def test_padrao_vazio_levanta_erro():
    with pytest.raises(ValueError):
        Regra("   ", "Transporte")


def test_regex_invalida_levanta_erro():
    with pytest.raises(ValueError):
        Regra("(", "Transporte", tipo="regex")
