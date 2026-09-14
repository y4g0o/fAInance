from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo.db import aplicar_vistas, criar_engine, escrita
from personalos.nucleo.modulo import Vista


def test_cria_tabelas_dos_metadados_informados(tmp_path: Path):
    engine = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,))
    nomes = set(inspect(engine).get_table_names())
    assert "financas_transacoes" in nomes
    assert "financas_regras" in nomes
    assert "nucleo_migracoes" in nomes


def test_sem_metadados_cria_so_as_tabelas_do_kernel(tmp_path: Path):
    # Sem metadados de módulo, nenhuma tabela de módulo aparece — só as do kernel,
    # que existem sempre (migrações, memória, insights).
    engine = criar_engine(tmp_path / "t.db")
    nomes = set(inspect(engine).get_table_names())
    assert nomes == {"nucleo_migracoes", "nucleo_memoria", "nucleo_insights"}


def test_pragmas_aplicados(tmp_path: Path):
    engine = criar_engine(tmp_path / "t.db")
    with engine.connect() as conn:
        modo = conn.execute(text("PRAGMA journal_mode")).scalar()
        fks = conn.execute(text("PRAGMA foreign_keys")).scalar()
    assert modo == "wal"
    assert fks == 1


def test_idempotente_chamar_duas_vezes(tmp_path: Path):
    caminho = tmp_path / "t.db"
    criar_engine(caminho, metadatas=(metadata_financas,))
    engine2 = criar_engine(caminho, metadatas=(metadata_financas,))  # não deve lançar exceção
    nomes = set(inspect(engine2).get_table_names())
    assert "financas_transacoes" in nomes


def test_aplicar_vistas_cria_view_consultavel(tmp_path):
    engine = criar_engine(tmp_path / "t.db")
    aplicar_vistas(engine, (Vista("vw_teste_v1", "SELECT 42 AS resposta"),))
    with engine.connect() as conn:
        valor = conn.execute(text("SELECT resposta FROM vw_teste_v1")).scalar()
    assert valor == 42


def test_aplicar_vistas_idempotente(tmp_path):
    engine = criar_engine(tmp_path / "t.db")
    vista = Vista("vw_teste_v1", "SELECT 42 AS resposta")
    aplicar_vistas(engine, (vista,))
    aplicar_vistas(engine, (vista,))  # não deve lançar exceção
    with engine.connect() as conn:
        valor = conn.execute(text("SELECT resposta FROM vw_teste_v1")).scalar()
    assert valor == 42


def test_criar_engine_aplica_vistas(tmp_path):
    vista = Vista("vw_teste_v1", "SELECT 7 AS resposta")
    engine = criar_engine(tmp_path / "t.db", vistas=(vista,))
    with engine.connect() as conn:
        valor = conn.execute(text("SELECT resposta FROM vw_teste_v1")).scalar()
    assert valor == 7


# ---------- endurecimento (achados da pesquisa de dados, verificados) ----------


def test_pragmas_de_desempenho_e_seguranca(tmp_path: Path):
    """synchronous=NORMAL é o default de produção com WAL: seguro contra corrupção
    (perde no máximo a última transação não-checkpointada) e sem fsync a cada commit.
    cache_size/mmap_size no default (2 MB / desligado) deixam I/O na mesa."""
    engine = criar_engine(tmp_path / "t.db")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA synchronous")).scalar() == 1  # NORMAL
        assert conn.execute(text("PRAGMA cache_size")).scalar() == -64000
        assert conn.execute(text("PRAGMA mmap_size")).scalar() == 268435456
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 15000


def test_aplicar_vistas_nao_recria_view_sem_mudanca(tmp_path: Path):
    """DROP VIEW + CREATE VIEW é DDL: pega write lock em sqlite_master e incrementa
    schema_version, invalidando prepared statements das outras conexões. Como
    criar_engine roda a cada processo, todo comando de CLI pagava esse preço."""
    # SQL multi-linha com indentação e newline final, como as vistas de verdade:
    # o SQLite descarta o espaço em branco final ao guardar o CREATE, então uma
    # comparação literal nunca casaria e a view seria recriada a cada processo.
    vistas = (Vista("vw_teste", "\n        SELECT 1 AS n\n        "),)
    caminho = tmp_path / "t.db"
    engine = criar_engine(caminho, vistas=vistas)
    with engine.connect() as conn:
        versao_inicial = conn.execute(text("PRAGMA schema_version")).scalar()

    aplicar_vistas(engine, vistas)  # mesmo SQL: não deve mexer no schema
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA schema_version")).scalar() == versao_inicial
        assert conn.execute(text("SELECT n FROM vw_teste")).scalar() == 1


def test_aplicar_vistas_recria_quando_o_sql_muda(tmp_path: Path):
    caminho = tmp_path / "t.db"
    engine = criar_engine(caminho, vistas=(Vista("vw_teste", "\n        SELECT 1 AS n\n        "),))
    aplicar_vistas(engine, (Vista("vw_teste", "\n        SELECT 2 AS n\n        "),))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT n FROM vw_teste")).scalar() == 2


def test_escrita_usa_begin_immediate(tmp_path: Path):
    """busy_timeout NÃO protege promoção de transação: se ela nasce em modo leitura
    e depois tenta escrever, o SQLite recusa na hora com SQLITE_BUSY. BEGIN IMMEDIATE
    pega o write lock na abertura, e aí o busy_timeout vale."""
    engine = criar_engine(tmp_path / "t.db")
    with escrita(engine) as conn:
        assert conn.execute(text("PRAGMA schema_version")).scalar() is not None
        conn.execute(text("CREATE TABLE t (x INTEGER)"))
        conn.execute(text("INSERT INTO t VALUES (1)"))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT x FROM t")).scalar() == 1


def test_escrita_desfaz_tudo_em_caso_de_erro(tmp_path: Path):
    engine = criar_engine(tmp_path / "t.db")
    with escrita(engine) as conn:
        conn.execute(text("CREATE TABLE t (x INTEGER)"))
    with pytest.raises(RuntimeError, match="falhou no meio"):
        with escrita(engine) as conn:
            conn.execute(text("INSERT INTO t VALUES (1)"))
            raise RuntimeError("falhou no meio")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM t")).scalar() == 0


def test_banco_e_diretorio_nascem_privados(tmp_path: Path):
    """O arquivo contém a vida financeira inteira: ninguém além do dono lê.

    Sem isso, instalação nova cria com 644/755 (o default do SQLite e do mkdir,
    filtrado pelo umask) — foi exatamente o estado encontrado em produção.
    """
    caminho = tmp_path / "dados" / "personalos.db"
    criar_engine(caminho)
    assert (caminho.parent.stat().st_mode & 0o777) == 0o700
    assert (caminho.stat().st_mode & 0o777) == 0o600


def test_permissao_e_corrigida_em_banco_preexistente(tmp_path: Path):
    caminho = tmp_path / "dados" / "personalos.db"
    caminho.parent.mkdir(parents=True)
    caminho.parent.chmod(0o755)
    caminho.touch()
    caminho.chmod(0o644)
    criar_engine(caminho)
    assert (caminho.parent.stat().st_mode & 0o777) == 0o700
    assert (caminho.stat().st_mode & 0o777) == 0o600


def test_banco_em_diretorio_de_outro_dono_nao_quebra():
    """O endurecimento de permissão não pode derrubar a aplicação.

    Bug real: `--db /tmp/x.db` fazia chmod em /tmp (do root) e levantava
    PermissionError, matando o servidor no boot. Apertar o que não é nosso não é
    nossa alçada; falhar por isso, muito menos.
    """
    import os

    caminho = Path("/tmp") / f"personalos_teste_{os.getpid()}.db"
    try:
        engine = criar_engine(caminho)  # não deve levantar
        with engine.connect() as conn:
            assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert (caminho.stat().st_mode & 0o777) == 0o600  # o arquivo, sim, é nosso
    finally:
        for sufixo in ("", "-wal", "-shm"):
            caminho.with_name(caminho.name + sufixo).unlink(missing_ok=True)
