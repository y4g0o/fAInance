from pathlib import Path

import pytest

from personalos.modulos.financas.infra.repositorios import RepoRegrasSQL, RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo.db import criar_engine


@pytest.fixture()
def engine(tmp_path: Path):
    return criar_engine(tmp_path / "teste.db", metadatas=(metadata_financas,))


@pytest.fixture()
def repo_transacoes(engine):
    return RepoTransacoesSQL(engine)


@pytest.fixture()
def repo_regras(engine):
    return RepoRegrasSQL(engine)

