"""Primitiva de transação de escrita. Mora sozinha porque `db.py` e `migracoes.py`
precisam dela e `db.py` já importa `migracoes.py` — colocá-la em qualquer um dos dois
fecharia um ciclo de import.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.engine import Connection, Engine


@contextmanager
def escrita(engine: Engine) -> Iterator[Connection]:
    """Transação de escrita que abre com BEGIN IMMEDIATE.

    Por que não `engine.begin()`: uma transação que nasce em modo leitura (o default
    DEFERRED) e depois tenta escrever precisa ser promovida, e o SQLite **recusa a
    promoção na hora, ignorando o `busy_timeout`** — permitir isso violaria a
    serializabilidade. Ou seja, o padrão "lê, decide, escreve" falha instantaneamente
    sob concorrência, e nenhum timeout salva. IMMEDIATE pega o write lock já na
    abertura, e aí o `busy_timeout` passa a valer.

    Use em todo caminho que decide o que gravar a partir do que leu (migrações,
    categorização na importação, aprendizado de gastos fixos).
    """
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.exec_driver_sql("ROLLBACK")
            raise
        conn.exec_driver_sql("COMMIT")
