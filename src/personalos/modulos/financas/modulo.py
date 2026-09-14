"""Manifesto do módulo financas — o que ele expõe ao kernel."""
from __future__ import annotations

from typing import TYPE_CHECKING

from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.aplicacao.resumo import resumo
from personalos.modulos.financas.cli import app as financas_cli
from personalos.modulos.financas.infra.tabelas import metadata
from personalos.modulos.financas.insights import REGRAS
from personalos.nucleo.modulo import Modulo

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import APIRouter


def _criar_router() -> "APIRouter":
    """Import tardio: FastAPI custa ~330 ms e a CLI carrega este manifesto sempre."""
    from personalos.modulos.financas.api import criar_router

    return criar_router()

MODULO = Modulo(
    nome="financas",
    metadata=metadata,
    cli=financas_cli,
    vistas=VISTAS,
    regras_insights=REGRAS,
    card=resumo,
    criar_router=_criar_router,
)
