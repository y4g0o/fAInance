from decimal import Decimal

import pytest

from personalos.modulos.financas.dominio.dinheiro import Dinheiro


def test_de_texto_br():
    assert Dinheiro.de_texto("1.234,56").centavos == 123456
    assert Dinheiro.de_texto("R$ 1.234,56").centavos == 123456
    assert Dinheiro.de_texto("-0,50").centavos == -50
    assert Dinheiro.de_texto("789,00").centavos == 78900


def test_de_texto_us():
    assert Dinheiro.de_texto("1234.56").centavos == 123456
    assert Dinheiro.de_texto("1234").centavos == 123400


def test_de_texto_us_com_milhar():
    assert Dinheiro.de_texto("12,345.67").centavos == 1234567


def test_de_decimal_arredonda():
    assert Dinheiro.de_decimal(Decimal("10.005")).centavos == 1001  # HALF_UP


def test_de_decimal_arredonda_negativo():
    assert Dinheiro.de_decimal(Decimal("-10.005")).centavos == -1001


def test_aritmetica():
    assert (Dinheiro(100) + Dinheiro(50)).centavos == 150
    assert (Dinheiro(100) - Dinheiro(150)).centavos == -50


def test_formatar_br():
    assert Dinheiro(123456).formatar() == "R$ 1.234,56"
    assert Dinheiro(-50).formatar() == "-R$ 0,50"


def test_imutavel():
    d = Dinheiro(10)
    with pytest.raises(Exception):
        d.centavos = 20  # type: ignore[misc]
