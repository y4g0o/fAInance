"""Tabelas do módulo financas (SQLAlchemy Core). Prefixo financas_ evita colisão
de namespace com outros módulos — SQLite não tem schemas."""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

transacoes = Table(
    "financas_transacoes",
    metadata,
    Column("fit_id", String, primary_key=True),
    Column("data", Date, nullable=False),
    Column("valor_centavos", BigInteger, nullable=False),
    Column("descricao", String, nullable=False, default=""),
    Column("conta", String, nullable=False),
    Column("categoria", String, nullable=True),
)

regras = Table(
    "financas_regras",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("padrao", String, nullable=False),
    Column("categoria", String, nullable=False),
    Column("tipo", String, nullable=False, default="contem"),
    Column("prioridade", Integer, nullable=False, default=100),
    UniqueConstraint("padrao", "tipo", name="uq_financas_regra"),
)

contas = Table(
    "financas_contas",
    metadata,
    Column("nome", String, primary_key=True),
    Column("saldo_inicial_centavos", BigInteger, nullable=False, default=0),
)
