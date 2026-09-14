"""Contrato de módulo do PersonalOS — dados, não framework.

O "registro de módulos" é uma tupla estática (ver personalos/composicao.py); plugar um
módulo novo é adicionar um manifesto Modulo à tupla, não implementar uma interface
com métodos. Campos são adicionados aqui só quando uma fatia do roadmap os usa de
verdade (ver docs/adr/0006-composition-root-fora-do-kernel.md).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import typer
from sqlalchemy import MetaData
from sqlalchemy.engine import Engine

if TYPE_CHECKING:  # pragma: no cover
    # Só para o mypy. Importar FastAPI em runtime aqui custaria ~330 ms (medido) em
    # TODO comando de CLI, porque composicao.py carrega os manifestos na importação.
    from fastapi import APIRouter


@dataclass(frozen=True)
class Vista:
    nome: str
    sql: str


@dataclass(frozen=True)
class Insight:
    """Um alerta concreto. modulo e regra_id são preenchidos pelo motor a partir da
    regra que o produziu — a regra não repete a própria identidade."""

    chave_dedup: str  # ex: "netflix:2026-07" — define o que conta como "o mesmo insight"
    titulo: str
    detalhe: dict[str, object] = field(default_factory=dict)
    severidade: str = "info"  # info|atencao|alerta


@dataclass(frozen=True)
class RegraInsight:
    """Regra determinística: lê o banco e devolve insights. Sem LLM, sem rede."""

    id: str
    avaliar: Callable[[Engine], list[Insight]]


@dataclass(frozen=True)
class Metrica:
    """Uma linha do card de um módulo no painel."""

    rotulo: str
    valor: str  # JÁ formatado pelo módulo — o template não sabe o que é centavo
    centavos: int | None = None  # valor cru, para gráfico; nunca para o HTML somar
    detalhe: str | None = None  # "base: 4 meses fechados"
    tom: str = "neutro"  # neutro|bom|atencao|alerta — semântica, não cor


@dataclass(frozen=True)
class CardResumo:
    """O que um módulo mostra no Resumo Geral.

    `vazio` é decisão do MÓDULO: só o financas sabe que zero mês fechado significa
    "sem base para afirmar", e não "R$ 0,00". O painel obedece, não interpreta — e
    `aviso` carrega a instrução do próprio módulo, que é como a tela de primeiro uso
    funciona sem o template conhecer módulo nenhum.
    """

    modulo: str  # casa com Modulo.nome
    titulo: str
    metricas: tuple[Metrica, ...] = ()
    vazio: bool = False
    aviso: str | None = None


@dataclass(frozen=True)
class Modulo:
    nome: str
    metadata: MetaData
    cli: typer.Typer | None = None
    vistas: tuple[Vista, ...] = ()
    regras_insights: tuple[RegraInsight, ...] = ()
    # Fábrica, não instância: ver o comentário de TYPE_CHECKING acima.
    criar_router: Callable[[], "APIRouter"] | None = None
    card: Callable[[Engine], CardResumo] | None = None
