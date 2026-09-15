"""Casos de uso de escrita do módulo financas.

Estas funções nasceram dentro do `cli.py`, onde a API não conseguia alcançá-las
sem duplicar regra. O que se testa aqui é o comportamento que a CLI já tinha —
os testes de CLI seguem verdes sem alteração, e são a prova de que a extração
não mudou nada.
"""
from __future__ import annotations

from datetime import date

from personalos.modulos.financas.aplicacao import escrita


def test_lancar_despesa_grava_com_sinal_negativo(repo_transacoes, repo_regras):
    """O valor entra como magnitude positiva; quem decide o sinal é o tipo.

    É a defesa que torna erro de sinal impossível, e o motivo de a API não poder
    reimplementar isso por fora.
    """
    resultado = escrita.lancar(
        repo_transacoes,
        repo_regras,
        descricao="cafe",
        valor="7,50",
        tipo="despesa",
        quando=date(2026, 9, 14),
    )

    assert resultado.inserida is True
    assert resultado.transacao.valor.centavos == -750


def test_lancar_recusa_tipo_desconhecido(repo_transacoes, repo_regras):
    """Sem isso, um tipo errado viraria receita silenciosamente — o `else` do
    sinal aceita qualquer coisa que não seja 'despesa'."""
    import pytest

    with pytest.raises(ValueError, match="tipo"):
        escrita.lancar(
            repo_transacoes,
            repo_regras,
            descricao="cafe",
            valor="7,50",
            tipo="saida",
            quando=date(2026, 9, 14),
        )


def test_lancar_recusa_valor_nao_positivo(repo_transacoes, repo_regras):
    """Valor zero ou negativo significa que alguém tentou codificar o sinal no
    número. O sinal é do tipo; aceitar isso abriria a porta pro erro de 100%."""
    import pytest

    with pytest.raises(ValueError, match="positivo"):
        escrita.lancar(
            repo_transacoes,
            repo_regras,
            descricao="cafe",
            valor="0",
            tipo="despesa",
            quando=date(2026, 9, 14),
        )


def test_lancar_sem_categoria_aplica_as_regras(repo_transacoes, repo_regras):
    """Lançar 'uber' com uma regra de uber cadastrada já nasce categorizado —
    caso contrário o lançamento manual seria o único caminho que ignora as
    regras, e a tela teria que recategorizar depois."""
    from personalos.modulos.financas.dominio.modelos import Regra

    repo_regras.adicionar(Regra("uber", "Transporte", "contem", 100))

    resultado = escrita.lancar(
        repo_transacoes,
        repo_regras,
        descricao="uber pro trabalho",
        valor="23,40",
        tipo="despesa",
        quando=date(2026, 9, 14),
    )

    assert resultado.transacao.categoria == "Transporte"


def test_lancar_o_mesmo_duas_vezes_nao_duplica(repo_transacoes, repo_regras):
    """O fit_id vem do conteúdo, então repetir o lançamento do mesmo dia é dedup.
    O comportamento vem do INSERT OR IGNORE do repositório — este teste existe
    para que uma mudança lá não passe despercebida."""
    args = dict(
        descricao="cafe", valor="7,50", tipo="despesa", quando=date(2026, 9, 14)
    )
    primeira = escrita.lancar(repo_transacoes, repo_regras, **args)
    segunda = escrita.lancar(repo_transacoes, repo_regras, **args)

    assert primeira.inserida is True
    assert segunda.inserida is False
    assert len(repo_transacoes.listar()) == 1


def test_definir_saldo_inicial_aceita_texto_brasileiro(engine):
    """A tela vai mandar '1.234,56' como o humano digita — o parse é do domínio,
    não da borda, senão CLI e API divergem no primeiro formato estranho."""
    from personalos.modulos.financas.infra.repositorios import RepoContasSQL

    repo = RepoContasSQL(engine)
    escrita.definir_saldo_conta(repo, nome="itau", saldo_inicial="1.234,56")

    assert dict((n, d.centavos) for n, d in repo.listar())["itau"] == 123456


def test_adicionar_regra_repetida_avisa_em_vez_de_duplicar(repo_regras):
    """Criar a mesma regra duas vezes não é erro do usuário — a tela vai ligar o
    checkbox 'criar regra' por padrão, então repetição é o caso comum, e precisa
    ser informada sem virar exceção."""
    assert escrita.adicionar_regra(repo_regras, padrao="uber", categoria="Transporte") is True
    assert escrita.adicionar_regra(repo_regras, padrao="uber", categoria="Transporte") is False


def _tx_simples(fit, descricao, categoria=None):
    from personalos.modulos.financas.dominio.dinheiro import Dinheiro
    from personalos.modulos.financas.dominio.modelos import Transacao

    return Transacao(fit, date(2026, 9, 14), Dinheiro(-1000), descricao, "conta", categoria)


def test_categorizar_grupo_devolve_os_fit_ids_que_mudou(repo_transacoes, repo_regras):
    """A tela precisa saber exatamente o que mudou para poder desfazer. Devolver
    a lista é o que sustenta o rollback — sem ela, desfazer seria adivinhação."""
    repo_transacoes.inserir_muitas(
        [
            _tx_simples("a1", "PIX QRS DELIVERIA BR"),
            _tx_simples("a2", "PIX QRS DELIVERIA BR"),
            _tx_simples("b1", "PIX QRS TELECOMIX"),
        ]
    )

    resultado = escrita.categorizar_grupo(
        repo_transacoes, repo_regras, padrao="deliveria", categoria="Delivery", criar_regra=False
    )

    assert sorted(resultado.fit_ids) == ["a1", "a2"]
    assert resultado.regra_criada is False


def test_categorizar_grupo_nao_sobrescreve_categoria_ja_atribuida(repo_transacoes, repo_regras):
    """Mesma regra do `recategorizar`: sobrescrever o que o humano ajustou à mão
    é destruir trabalho dele."""
    repo_transacoes.inserir_muitas(
        [
            _tx_simples("a1", "PIX QRS DELIVERIA BR"),
            _tx_simples("a2", "PIX QRS DELIVERIA BR", categoria="Presente"),
        ]
    )

    resultado = escrita.categorizar_grupo(
        repo_transacoes, repo_regras, padrao="deliveria", categoria="Delivery", criar_regra=False
    )

    assert resultado.fit_ids == ["a1"]
    por_fit = {t.fit_id: t.categoria for t in repo_transacoes.listar()}
    assert por_fit["a2"] == "Presente"


def test_desfazer_lote_volta_categorias_e_remove_a_regra_criada(repo_transacoes, repo_regras):
    """Desfazer que deixa a regra de pé é desfazer mentiroso: o próximo
    `recategorizar` reaplicaria tudo, e o usuário veria a categoria voltar
    sozinha sem entender por quê."""
    repo_transacoes.inserir_muitas(
        [_tx_simples("a1", "PIX QRS DELIVERIA BR"), _tx_simples("a2", "PIX QRS DELIVERIA BR")]
    )
    aplicado = escrita.categorizar_grupo(
        repo_transacoes, repo_regras, padrao="deliveria", categoria="Delivery", criar_regra=True
    )
    assert aplicado.regra_criada is True

    escrita.desfazer_lote(
        repo_transacoes, repo_regras, fit_ids=aplicado.fit_ids, padrao_da_regra="deliveria"
    )

    assert all(t.categoria is None for t in repo_transacoes.listar())
    assert [r.padrao for r in repo_regras.listar()] == []


def test_renomear_categoria_junta_as_variantes(repo_transacoes, repo_regras):
    """'compras' e 'Compras' viram fatias separadas do mesmo gasto no relatório.
    Aconteceu de verdade: o campo é texto livre e não mostra o que já existe."""
    repo_transacoes.inserir_muitas(
        [
            _tx_simples("a1", "LOJA UM", categoria="compras"),
            _tx_simples("a2", "LOJA DOIS", categoria="Compras"),
            _tx_simples("b1", "OUTRA COISA", categoria="Telefonia"),
        ]
    )

    mudadas = escrita.renomear_categoria(repo_transacoes, de="compras", para="Compras")

    assert mudadas == 1
    por_categoria = {t.fit_id: t.categoria for t in repo_transacoes.listar()}
    assert por_categoria["a1"] == "Compras"
    assert por_categoria["b1"] == "Telefonia"
