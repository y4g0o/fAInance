"""Atualização de categoria no repositório.

Hoje o único caminho que muda categoria é o UPDATE inline dentro de
`recategorizar`. A tela precisa mudar UMA transação e um GRUPO delas, e SQL
espalhado por casos de uso é como a convenção de sinal se perde.
"""
from __future__ import annotations

from datetime import date

from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao


def _tx(fit: str, descricao: str, centavos: int = -1000) -> Transacao:
    return Transacao(fit, date(2026, 9, 14), Dinheiro(centavos), descricao, "conta", None)


def test_definir_categoria_muda_uma_transacao(repo_transacoes):
    repo_transacoes.inserir_muitas([_tx("a1", "PIX QRS DELIVERIA")])

    mudadas = repo_transacoes.definir_categoria(["a1"], "Delivery")

    assert mudadas == 1
    assert repo_transacoes.listar()[0].categoria == "Delivery"


def test_definir_categoria_de_fit_id_inexistente_nao_muda_nada(repo_transacoes):
    """Devolver o número real de linhas afetadas é o que permite à tela desfazer
    exatamente o que mudou — e não mentir sobre o que aconteceu."""
    repo_transacoes.inserir_muitas([_tx("a1", "PIX QRS DELIVERIA")])

    assert repo_transacoes.definir_categoria(["nao-existe"], "Delivery") == 0
    assert repo_transacoes.listar()[0].categoria is None
