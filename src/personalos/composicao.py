"""Composition root do PersonalOS: onde os módulos são plugados.

Plugar um módulo novo = adicionar seu manifesto aqui. Sem discovery dinâmico: com
poucos módulos mantidos por uma única pessoa, uma lista explícita é mais simples e
mais fácil de depurar do que um mecanismo de plugin.

**Por que fora de `nucleo/`:** este arquivo importa os módulos, e o kernel não pode
depender deles — é a direção errada da dependência. Enquanto isso morava em
`nucleo/registro.py`, o kernel nunca era independente dos módulos, e com uma dezena
deles isso viraria um nó impossível de desatar. Composition root é a única camada
que conhece todo mundo, e por isso vive na borda, não no centro.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from personalos.modulos.financas.modulo import MODULO as FINANCAS
from personalos.nucleo.modulo import Modulo

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.engine import Engine

MODULOS: tuple[Modulo, ...] = (FINANCAS,)


def serie_mensal(engine: "Engine") -> list[dict[str, object]]:
    """Série temporal que o painel plota. Mora aqui, e não em `api/`, porque saber
    QUAL módulo fornece o gráfico é conhecimento de composição — a camada web tem de
    continuar agnóstica. Import tardio para não arrastar o módulo na importação.
    """
    from personalos.modulos.financas.aplicacao.consultas import fluxo_mensal

    return fluxo_mensal(engine)
