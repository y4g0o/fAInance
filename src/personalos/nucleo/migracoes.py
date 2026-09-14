"""Motor de migrações do PersonalOS — passos idempotentes em Python puro.

Sem Alembic nesta fatia (gatilho de adoção: primeira mudança destrutiva de
schema que este mecanismo torne desconfortável — ver spec do v0.2)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from personalos.nucleo.transacao import escrita


@dataclass(frozen=True)
class Migracao:
    id: str
    aplicar: Callable[[Connection], None]


def _tabela_existe(conn: Connection, nome: str) -> bool:
    resultado = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:nome"),
        {"nome": nome},
    )
    return resultado.first() is not None


def _renomear_tabelas_v01(conn: Connection) -> None:
    if _tabela_existe(conn, "transacoes") and not _tabela_existe(conn, "financas_transacoes"):
        conn.execute(text("ALTER TABLE transacoes RENAME TO financas_transacoes"))
    if _tabela_existe(conn, "regras") and not _tabela_existe(conn, "financas_regras"):
        conn.execute(text("ALTER TABLE regras RENAME TO financas_regras"))


MIGRACOES: tuple[Migracao, ...] = (
    Migracao("001_prefixo_financas", _renomear_tabelas_v01),
)


def aplicar_migracoes(engine: Engine) -> None:
    # BEGIN IMMEDIATE: este é o padrão "lê a lista de aplicadas, decide, insere" —
    # exatamente o que o SQLite recusa promover de leitura para escrita.
    with escrita(engine) as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS nucleo_migracoes ("
                "id TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)"
            )
        )
        aplicadas = {row[0] for row in conn.execute(text("SELECT id FROM nucleo_migracoes"))}
        for migracao in MIGRACOES:
            if migracao.id in aplicadas:
                continue
            migracao.aplicar(conn)
            conn.execute(
                text("INSERT INTO nucleo_migracoes (id, aplicada_em) VALUES (:id, :agora)"),
                {"id": migracao.id, "agora": datetime.now(timezone.utc).isoformat()},
            )
