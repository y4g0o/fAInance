"""Engine compartilhada do PersonalOS.

PRAGMAs aplicados em toda conexão: WAL, `synchronous=NORMAL`, `busy_timeout`,
foreign keys, cache de 64 MB e mmap de 256 MB — ver os comentários em
`_configurar_pragmas` para o porquê de cada um.

Recebe os metadados e as views dos módulos como parâmetro (em vez de importar
composicao diretamente) para evitar um import circular: composicao→modulo
do financas→cli do financas→(voltaria a) db, se db importasse composicao.

Escrita transacional fica em `nucleo/transacao.py` (BEGIN IMMEDIATE), num módulo
separado porque `migracoes.py` também precisa dela e este arquivo já a importa."""
from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import MetaData, create_engine, event, text
from sqlalchemy.engine import Engine

from personalos.nucleo.migracoes import aplicar_migracoes
from personalos.nucleo.modulo import Vista
from personalos.nucleo.tabelas import metadata as metadata_nucleo
from personalos.nucleo.transacao import escrita


def aplicar_vistas(engine: Engine, vistas: Sequence[Vista]) -> None:
    """Recria apenas as views cujo SQL mudou.

    `DROP VIEW`/`CREATE VIEW` é DDL: exige write lock em `sqlite_master` e
    incrementa `schema_version`, o que invalida os prepared statements de todas as
    outras conexões abertas. Como `criar_engine` roda uma vez por processo, a
    versão anterior fazia **todo comando de CLI** pagar esse preço e disputar lock
    com o painel. Comparando com o SQL já registrado, o caminho normal fica
    read-only.
    """
    with engine.connect() as conn:
        registrado = {
            nome: sql
            for nome, sql in conn.execute(
                text("SELECT name, sql FROM sqlite_master WHERE type = 'view'")
            )
        }
    # rstrip nos dois lados: o SQLite guarda o texto original do CREATE, mas
    # **descarta o espaço em branco final** — e o SQL das vistas é string de várias
    # linhas, que termina em newline + indentação. Sem isso, a comparação nunca casa
    # e as 7 views são recriadas a cada processo (medido: 14 bumps de schema_version
    # por comando de CLI).
    def _canonico(nome: str, sql: str) -> str:
        return f"CREATE VIEW {nome} AS {sql}".rstrip()

    desatualizadas = [
        v
        for v in vistas
        if (registrado.get(v.nome) or "").rstrip() != _canonico(v.nome, v.sql)
    ]
    if not desatualizadas:
        return
    with escrita(engine) as conn:
        for vista in desatualizadas:
            conn.execute(text(f"DROP VIEW IF EXISTS {vista.nome}"))
            conn.execute(text(f"CREATE VIEW {vista.nome} AS {vista.sql}"))


def criar_engine(
    caminho_db: Path,
    metadatas: Sequence[MetaData] = (),
    vistas: Sequence[Vista] = (),
) -> Engine:
    caminho_db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    engine = create_engine(f"sqlite:///{caminho_db}")

    @event.listens_for(engine, "connect")
    def _configurar_pragmas(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        # NORMAL é o default recomendado com WAL: sem fsync a cada commit e ainda
        # seguro contra corrupção — no pior caso perde a última transação que ainda
        # não foi para o checkpoint. FULL (o default compilado aqui) paga fsync
        # sempre, o que não se justifica para dado que também vai para o restic.
        cursor.execute("PRAGMA synchronous=NORMAL")
        # 5 s era pouco: ingestão de PDF segura o writer por mais tempo que isso.
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA cache_size=-64000")  # 64 MB (default: 2 MB)
        cursor.execute("PRAGMA mmap_size=268435456")  # 256 MB (default: desligado)
        cursor.close()

    aplicar_migracoes(engine)
    metadata_nucleo.create_all(engine)  # tabelas do kernel existem sempre
    for metadata in metadatas:
        metadata.create_all(engine)
    aplicar_vistas(engine, vistas)
    _restringir_permissoes(caminho_db)
    return engine


def _restringir_permissoes(caminho_db: Path) -> None:
    """Menor privilégio no banco: 700 no diretório, 600 nos arquivos.

    O `mode=` do mkdir é filtrado pelo umask e não corrige diretório que já existe,
    e o SQLite cria o arquivo com 644 & ~umask. Sem este passo, uma instalação nova
    deixa a vida financeira do usuário legível por qualquer conta da máquina — foi
    o estado encontrado em produção (664 no banco, 775 no diretório).
    Roda depois de abrir, porque só então os arquivos -wal e -shm existem.

    Aperta apenas o que é NOSSO: um `--db /tmp/x.db` tem `/tmp` como pai, que é do
    root — tentar apertá-lo levantava PermissionError e derrubava o servidor no boot.
    Proteger diretório de terceiro não é alçada deste programa.
    """
    pai = caminho_db.parent
    if pai.stat().st_uid == os.getuid():
        pai.chmod(0o700)
    for sufixo in ("", "-wal", "-shm"):
        arquivo = caminho_db.with_name(caminho_db.name + sufixo)
        if arquivo.exists() and arquivo.stat().st_uid == os.getuid():
            arquivo.chmod(0o600)
