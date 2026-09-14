"""Montagem do que o painel exibe — função PURA, sem HTML e sem HTTP.

Toda a lógica de "o que aparece" vive aqui, para ser testada sem Jinja e sem
TestClient: quantos cards, quais estão vazios, que seção fica oculta, que sinais
o gráfico recebe. O template só itera.

O painel **não conhece módulo nenhum**: os cards vêm de `Modulo.card`. Existe um
teste de arquitetura que falha o build se o nome de um módulo aparecer em painel/.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.engine import Engine

from personalos.nucleo import insights as motor_insights
from personalos.nucleo.modulo import CardResumo, Modulo


@dataclass(frozen=True)
class ContextoPainel:
    cards: tuple[CardResumo, ...]
    fluxo: tuple[Mapping[str, Any], ...]
    insights: tuple[Any, ...]
    chat_disponivel: bool

    @property
    def tem_grafico(self) -> bool:
        return len(self.fluxo) >= 2  # um mês só não é série

    @property
    def tem_insights(self) -> bool:
        return bool(self.insights)

    @property
    def primeiro_uso(self) -> bool:
        """Todo card vazio: é instalação nova, e a tela deve ensinar, não zerar."""
        return bool(self.cards) and all(c.vazio for c in self.cards)


def montar_contexto(
    engine: Engine,
    modulos: Sequence[Modulo],
    chat_disponivel: bool = False,
    fluxo: Sequence[Mapping[str, Any]] = (),
) -> ContextoPainel:
    cards = tuple(m.card(engine) for m in modulos if m.card is not None)
    return ContextoPainel(
        cards=cards,
        fluxo=tuple(fluxo),
        insights=tuple(motor_insights.listar(engine, status="novo")),
        chat_disponivel=chat_disponivel,
    )
