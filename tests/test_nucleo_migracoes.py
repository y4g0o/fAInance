from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from personalos.nucleo.migracoes import aplicar_migracoes


def _criar_schema_v01(caminho_db: Path) -> None:
    """Simula um banco real do v0.1, antes do prefixo financas_."""
    engine = create_engine(f"sqlite:///{caminho_db}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE transacoes (fit_id TEXT PRIMARY KEY, data DATE, "
            "valor_centavos INTEGER, descricao TEXT, conta TEXT, categoria TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE regras (id INTEGER PRIMARY KEY, padrao TEXT, "
            "categoria TEXT, tipo TEXT, prioridade INTEGER)"
        ))
        conn.execute(text(
            "INSERT INTO transacoes VALUES ('a', '2026-06-01', -1000, 'uber', 'nubank', NULL)"
        ))
    engine.dispose()


def test_migra_schema_v01_para_prefixado(tmp_path: Path):
    caminho_db = tmp_path / "v01.db"
    _criar_schema_v01(caminho_db)

    engine = create_engine(f"sqlite:///{caminho_db}")
    aplicar_migracoes(engine)

    nomes_tabelas = set(inspect(engine).get_table_names())
    assert "financas_transacoes" in nomes_tabelas
    assert "financas_regras" in nomes_tabelas
    assert "transacoes" not in nomes_tabelas
    assert "regras" not in nomes_tabelas

    with engine.connect() as conn:
        linhas = conn.execute(text("SELECT fit_id FROM financas_transacoes")).fetchall()
    assert [r[0] for r in linhas] == ["a"]


def test_aplicar_migracoes_e_idempotente(tmp_path: Path):
    caminho_db = tmp_path / "v01.db"
    _criar_schema_v01(caminho_db)
    engine = create_engine(f"sqlite:///{caminho_db}")

    aplicar_migracoes(engine)
    aplicar_migracoes(engine)  # segunda chamada não deve falhar nem duplicar

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM financas_transacoes")).scalar()
        aplicadas = conn.execute(text("SELECT COUNT(*) FROM nucleo_migracoes")).scalar()
    assert total == 1
    assert aplicadas == 1


def test_banco_novo_sem_tabelas_antigas_nao_falha(tmp_path: Path):
    """Um banco novo (sem transacoes/regras não-prefixadas) deve passar sem erro."""
    caminho_db = tmp_path / "novo.db"
    engine = create_engine(f"sqlite:///{caminho_db}")
    aplicar_migracoes(engine)  # não deve lançar exceção
    nomes_tabelas = set(inspect(engine).get_table_names())
    assert "nucleo_migracoes" in nomes_tabelas
    assert "financas_transacoes" not in nomes_tabelas
