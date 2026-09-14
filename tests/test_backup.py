import shutil
import sqlite3
from datetime import date
from pathlib import Path

from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo.backup import fazer_backup
from personalos.nucleo.db import criar_engine


def _semear(caminho_db: Path) -> None:
    engine = criar_engine(caminho_db, metadatas=(metadata_financas,))
    repo = RepoTransacoesSQL(engine)
    repo.inserir_muitas(
        [Transacao("a", date(2026, 6, 1), Dinheiro(-1000), "teste", "nubank")]
    )


def test_backup_preserva_dados(tmp_path: Path):
    db_original = tmp_path / "original.db"
    _semear(db_original)

    caminho_backup = fazer_backup(db_original, tmp_path / "backups")

    assert caminho_backup.exists()
    engine_backup = criar_engine(caminho_backup, metadatas=(metadata_financas,))
    repo_backup = RepoTransacoesSQL(engine_backup)
    assert len(repo_backup.listar()) == 1
    assert repo_backup.listar()[0].fit_id == "a"


def test_nome_do_backup_tem_carimbo_de_data_hora(tmp_path: Path):
    db_original = tmp_path / "original.db"
    _semear(db_original)
    caminho_backup = fazer_backup(db_original, tmp_path / "backups")
    assert caminho_backup.name.startswith("personalos-")
    assert caminho_backup.suffix == ".db"


def test_restaura_apos_perda_do_original(tmp_path: Path):
    """Simula perda do banco original e restauração a partir do backup."""
    db_original = tmp_path / "original.db"
    _semear(db_original)

    caminho_backup = fazer_backup(db_original, tmp_path / "backups")
    db_original.unlink()
    assert not db_original.exists()

    shutil.copy(caminho_backup, db_original)
    engine_restaurado = criar_engine(db_original, metadatas=(metadata_financas,))
    repo_restaurado = RepoTransacoesSQL(engine_restaurado)
    assert len(repo_restaurado.listar()) == 1


def test_backup_nasce_privado(tmp_path):
    """Cópia do banco é tão sensível quanto o banco: 700 no diretório, 600 no arquivo."""
    origem = tmp_path / "origem.db"
    sqlite3.connect(origem).close()
    destino_dir = tmp_path / "backups"
    destino = fazer_backup(origem, destino_dir)
    assert (destino_dir.stat().st_mode & 0o777) == 0o700
    assert (destino.stat().st_mode & 0o777) == 0o600
