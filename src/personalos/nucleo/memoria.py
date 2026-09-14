"""Memória do PersonalOS — fatos aprendidos ou declarados, por módulo.

Um fato é (modulo, tipo, chave) → valor JSON. Tipar o valor é responsabilidade de
quem lê (o formato de um gasto_fixo é assunto do módulo financas, não do kernel).
Regravar a mesma chave atualiza o valor: aprender de novo não duplica.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from personalos.nucleo.tabelas import memoria as t_memoria


@dataclass(frozen=True)
class Fato:
    modulo: str
    tipo: str
    chave: str
    valor: dict[str, object]
    atualizado_em: str


def definir(
    engine: Engine, modulo: str, tipo: str, chave: str, valor: dict[str, object]
) -> None:
    """Upsert de um fato (o UNIQUE de (modulo, tipo, chave) é a identidade)."""
    agora = datetime.now(timezone.utc).isoformat()
    stmt = sqlite_insert(t_memoria).values(
        modulo=modulo, tipo=tipo, chave=chave, valor=json.dumps(valor), atualizado_em=agora
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["modulo", "tipo", "chave"],
        set_={"valor": stmt.excluded.valor, "atualizado_em": agora},
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def listar(engine: Engine, modulo: str | None = None, tipo: str | None = None) -> list[Fato]:
    consulta = select(t_memoria).order_by(t_memoria.c.modulo, t_memoria.c.tipo, t_memoria.c.chave)
    if modulo is not None:
        consulta = consulta.where(t_memoria.c.modulo == modulo)
    if tipo is not None:
        consulta = consulta.where(t_memoria.c.tipo == tipo)
    with engine.connect() as conn:
        return [
            Fato(r.modulo, r.tipo, r.chave, json.loads(r.valor), r.atualizado_em)
            for r in conn.execute(consulta)
        ]


def remover(engine: Engine, modulo: str, tipo: str, chave: str) -> bool:
    """Esquece um fato (ex: um 'gasto fixo' que o detector inventou). True se existia."""
    with engine.begin() as conn:
        resultado = conn.execute(
            delete(t_memoria).where(
                t_memoria.c.modulo == modulo,
                t_memoria.c.tipo == tipo,
                t_memoria.c.chave == chave,
            )
        )
    return resultado.rowcount > 0
