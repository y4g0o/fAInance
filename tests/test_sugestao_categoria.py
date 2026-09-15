"""Sugerir categoria a partir do que o usuário JÁ categorizou.

A sugestão sai do histórico dele, não de um palpite: se 'SUPERMERCADO BOM PREÇO'
já está em Mercado, 'SUPERMERCADO SÃO JOSÉ' provavelmente também. E vem com a
evidência — qual palavra casou e em quantas transações — porque sugestão sem
justificativa é adivinhação com cara de autoridade.
"""
from datetime import date
from pathlib import Path

import pytest

from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.aplicacao.sugestoes import sugerir_categoria
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo.db import criar_engine


@pytest.fixture
def engine(tmp_path: Path):
    e = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    RepoTransacoesSQL(e).inserir_muitas(
        [
            Transacao("c1", date(2026, 5, 1), Dinheiro(-5000), "SUPERMERCADO BOM PRECO", "n", "Mercado"),
            Transacao("c2", date(2026, 5, 2), Dinheiro(-3000), "SUPERMERCADO CENTRAL", "n", "Mercado"),
            Transacao("c3", date(2026, 5, 3), Dinheiro(-2000), "POSTO IPIRANGA", "n", "Transporte"),
            Transacao("s1", date(2026, 6, 1), Dinheiro(-4000), "SUPERMERCADO SAO JOSE", "n", None),
            Transacao("s2", date(2026, 6, 2), Dinheiro(-1500), "LOJA DESCONHECIDA XPTO", "n", None),
        ]
    )
    return e


def test_sugere_a_categoria_que_o_usuario_ja_usou_para_a_mesma_palavra(engine):
    sugestao = sugerir_categoria(engine, "SUPERMERCADO SAO JOSE")

    assert sugestao is not None
    assert sugestao.categoria == "Mercado"
    assert sugestao.palavra == "supermercado"
    assert sugestao.transacoes == 2


def test_nao_sugere_quando_nao_ha_precedente(engine):
    """Sem base no histórico, o certo é não sugerir. Palpite com cara de sugestão
    é pior que campo vazio: o usuário confia e aceita."""
    assert sugerir_categoria(engine, "LOJA DESCONHECIDA XPTO") is None


def test_ignora_palavra_curta_e_generica(engine):
    """'DE', 'DA', 'COMPRA' aparecem em tudo e não identificam nada."""
    assert sugerir_categoria(engine, "COMPRA NO DEBITO") is None


def test_palavra_generica_com_acento_tambem_e_ignorada(tmp_path):
    """Falha real: a lista de genéricas tinha 'debito' sem acento, e o extrato
    escreve 'Compra no débito - LOJA'. Resultado: 'débito' virou a palavra mais
    distintiva de TODAS as descrições, e o sistema sugeriu Delivery para
    supermercado. Sugestão errada com justificativa convincente é pior que
    nenhuma — o usuário aceita."""
    e = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    RepoTransacoesSQL(e).inserir_muitas(
        [
            Transacao("c1", date(2026, 5, 1), Dinheiro(-3000), "Compra no débito - ACAI DO MANGUE", "n", "Delivery"),
            Transacao("c2", date(2026, 5, 2), Dinheiro(-3000), "Compra no débito - ACAI CENTRAL", "n", "Delivery"),
            Transacao("s1", date(2026, 6, 1), Dinheiro(-4000), "Compra no débito - SUPERMERCADO SAO JOSE", "n", None),
        ]
    )

    sugestao = sugerir_categoria(e, "Compra no débito - SUPERMERCADO SAO JOSE")

    assert sugestao is None, f"sugeriu {sugestao} por uma palavra que aparece em tudo"


def test_uma_ocorrencia_so_nao_sustenta_sugestao(tmp_path):
    """Uma coincidência não é padrão. O mesmo limiar do agrupador: 2."""
    e = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    RepoTransacoesSQL(e).inserir_muitas(
        [
            Transacao("c1", date(2026, 5, 1), Dinheiro(-3000), "PADARIA CENTRAL", "n", "Alimentação"),
            Transacao("s1", date(2026, 6, 1), Dinheiro(-4000), "PADARIA NOVA", "n", None),
        ]
    )

    assert sugerir_categoria(e, "PADARIA NOVA") is None


def test_nao_sugere_categoria_declarada_como_movimentacao(tmp_path):
    """Sugerir 'Conta de uso' para uma compra é sugerir que ela não é gasto —
    o oposto do que se quer, e o usuário aceitaria sem perceber."""
    from personalos.modulos.financas.aplicacao import escrita

    e = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    RepoTransacoesSQL(e).inserir_muitas(
        [
            Transacao(f"c{i}", date(2026, 5, i + 1), Dinheiro(-3000), f"ANCORA DISTRIBUIDORA {i}", "n", "Conta de uso")
            for i in range(3)
        ]
        + [Transacao("s1", date(2026, 6, 1), Dinheiro(-4000), "ANCORA DISTRIBUIDORA NOVA", "n", None)]
    )
    escrita.declarar_nao_consumo(e, "Conta de uso")

    assert sugerir_categoria(e, "ANCORA DISTRIBUIDORA NOVA") is None
