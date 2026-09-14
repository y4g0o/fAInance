"""Fábrica única de engine com tudo que os módulos registrados declaram.

Existe para que CLI, API e painel não possam divergir: se um deles esquecesse de
passar `vistas=`, todo endpoint que lê view daria 500 em banco novo ("no such
table: vw_financas_saldo_v1"). Mora fora de `nucleo/db.py` porque importa o
composition root, e `db.py` não pode (ver o docstring dele).
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine

from personalos.composicao import MODULOS
from personalos.nucleo.config import caminho_banco
from personalos.nucleo.db import criar_engine


def criar_engine_do_sistema(db: Path | None = None) -> Engine:
    return criar_engine(
        db or caminho_banco(),
        metadatas=tuple(m.metadata for m in MODULOS),
        vistas=tuple(v for m in MODULOS for v in m.vistas),
    )
