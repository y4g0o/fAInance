"""Casos de uso que ESCREVEM no módulo financas.

Moram aqui, e não na CLI, porque a API precisa da mesma operação: um endpoint que
reimplementasse a conversão de sinal ou a geração de `fit_id` divergiria da CLI no
primeiro ajuste, e divergência em dinheiro é erro silencioso.

Nenhuma função aqui conhece Typer, FastAPI ou HTTP — recebem dados e repositórios,
devolvem resultado, levantam `ValueError` com a mensagem que o humano precisa ler.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING
from datetime import date
from hashlib import sha1

from personalos.modulos.financas.aplicacao.portas import RepoRegras, RepoTransacoes
from personalos.modulos.financas.dominio.categorizador import categorizar
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Regra, Transacao

if TYPE_CHECKING:  # pragma: no cover - só para tipo
    from personalos.modulos.financas.infra.repositorios import RepoContasSQL as RepoContas


TIPOS = ("despesa", "receita")


@dataclass(frozen=True)
class ResultadoLancamento:
    transacao: Transacao
    inserida: bool


def fit_id_manual(quando: date, centavos: int, descricao: str, conta: str) -> str:
    """fit_id derivado do conteúdo: repetir o mesmo lançamento no mesmo dia é dedup."""
    digest = sha1(f"{quando}|{centavos}|{descricao.strip().lower()}|{conta}".encode()).hexdigest()
    return f"manual-{quando:%Y%m%d}-{digest[:10]}"


def lancar(
    repo_tx: RepoTransacoes,
    repo_regras: RepoRegras,
    *,
    descricao: str,
    valor: str,
    tipo: str,
    quando: date,
    conta: str = "manual",
    categoria: str | None = None,
) -> ResultadoLancamento:
    """Lança uma transação manual. O valor é MAGNITUDE; o sinal vem do tipo."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo inválido: {tipo!r} (use {'|'.join(TIPOS)})")
    magnitude = Dinheiro.de_texto(valor)
    if magnitude.centavos <= 0:
        raise ValueError("valor deve ser positivo (o sinal vem do tipo)")
    centavos = -magnitude.centavos if tipo == "despesa" else magnitude.centavos
    transacao = Transacao(
        fit_id=fit_id_manual(quando, centavos, descricao, conta),
        data=quando,
        valor=Dinheiro(centavos),
        descricao=descricao,
        conta=conta,
        categoria=categoria,
    )
    if transacao.categoria is None:
        transacao = replace(transacao, categoria=categorizar(transacao, repo_regras.listar()))
    inseridas = repo_tx.inserir_muitas([transacao])
    return ResultadoLancamento(transacao=transacao, inserida=inseridas == 1)


def definir_saldo_conta(repo_contas: RepoContas, *, nome: str, saldo_inicial: str) -> Dinheiro:
    """Define o saldo inicial de uma conta. Aceita o texto como o humano digita."""
    valor = Dinheiro.de_texto(saldo_inicial)
    repo_contas.definir_saldo_inicial(nome, valor)
    return valor


def adicionar_regra(
    repo_regras: RepoRegras,
    *,
    padrao: str,
    categoria: str,
    tipo: str = "contem",
    prioridade: int = 100,
) -> bool:
    """Adiciona uma regra. Devolve False se já existia — repetir não é erro.

    A validação de padrão e tipo é do domínio (`Regra`), que levanta ValueError.
    """
    return repo_regras.adicionar(Regra(padrao, categoria, tipo, prioridade))


@dataclass(frozen=True)
class ResultadoLote:
    fit_ids: list[str]
    regra_criada: bool


def categorizar_grupo(
    repo_tx: RepoTransacoes,
    repo_regras: RepoRegras,
    *,
    padrao: str,
    categoria: str,
    criar_regra: bool = True,
    tipo: str = "contem",
) -> ResultadoLote:
    """Aplica uma categoria a todas as transações SEM categoria que casam com o padrão.

    O cliente manda o padrão e o servidor recalcula o grupo: o agrupamento nunca
    sai de Python para o React, então a tela não pode divergir do que o sistema
    entende por "grupo".

    Devolve os fit_id efetivamente alterados — é com eles que a interface desfaz
    exatamente o que mudou, nem mais nem menos.

    Não sobrescreve categoria já atribuída, pela mesma razão de `recategorizar`:
    seria destruir ajuste manual do usuário.
    """
    if not padrao.strip():
        raise ValueError("padrão vazio: pegaria todas as transações de uma vez")
    regra = Regra(padrao, categoria, tipo, 100)
    alvos = [
        t.fit_id
        for t in repo_tx.listar()
        if t.categoria is None and categorizar(t, [regra]) is not None
    ]
    repo_tx.definir_categoria(alvos, categoria)
    regra_criada = adicionar_regra(
        repo_regras, padrao=padrao, categoria=categoria, tipo=tipo
    ) if criar_regra else False
    return ResultadoLote(fit_ids=alvos, regra_criada=regra_criada)


def desfazer_lote(
    repo_tx: RepoTransacoes,
    repo_regras: RepoRegras,
    *,
    fit_ids: list[str],
    padrao_da_regra: str | None = None,
    tipo: str = "contem",
) -> int:
    """Desfaz uma categorização em lote: tira a categoria e remove a regra criada.

    Desfazer que deixa a regra de pé é desfazer mentiroso — o próximo
    `recategorizar` reaplicaria tudo, e a categoria voltaria sozinha sem o
    usuário entender por quê.

    Devolve quantas transações voltaram a ficar sem categoria.
    """
    voltaram = repo_tx.definir_categoria(fit_ids, None)
    if padrao_da_regra:
        repo_regras.remover(padrao_da_regra, tipo)
    return voltaram
