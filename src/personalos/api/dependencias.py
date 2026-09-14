"""Dependências do FastAPI. Uma engine por aplicação, guardada no estado do app."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.engine import Engine

from personalos.nucleo.portas.chat import ServicoChat


def obter_engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


def obter_chat(request: Request) -> ServicoChat | None:
    servico: ServicoChat | None = request.app.state.chat
    return servico
