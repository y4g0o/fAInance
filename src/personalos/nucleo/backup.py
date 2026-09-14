"""Backup do banco do PersonalOS via API nativa de backup do SQLite (online,
consistente mesmo com o banco em uso — não é uma simples cópia de arquivo)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def fazer_backup(caminho_db: Path, diretorio_destino: Path) -> Path:
    """Cópia consistente do banco, nascendo privada (700 no diretório, 600 no arquivo).

    Uma cópia do banco é tão sensível quanto o banco. O default do mkdir e do SQLite
    deixa o arquivo legível por qualquer conta da máquina — e `mkdir(mode=)` não
    corrige diretório que já existe, daí o chmod explícito.
    """
    diretorio_destino.mkdir(parents=True, exist_ok=True, mode=0o700)
    diretorio_destino.chmod(0o700)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = diretorio_destino / f"personalos-{carimbo}.db"
    origem_conn = sqlite3.connect(caminho_db)
    destino_conn = sqlite3.connect(destino)
    try:
        origem_conn.backup(destino_conn)
    finally:
        origem_conn.close()
        destino_conn.close()
    destino.chmod(0o600)
    return destino
