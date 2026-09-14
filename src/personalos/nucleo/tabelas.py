"""Tabelas do kernel — existem sempre, independentes de quais módulos estão ativos.

Diferente das tabelas de módulo (que vêm de Modulo.metadata), estas são aplicadas
por criar_engine em todo banco: memória (fatos curados) e insights (alertas
determinísticos gerados pelas regras dos módulos).
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, String, Table, UniqueConstraint

metadata = MetaData()

# Fatos que o sistema aprendeu ou que o usuário declarou. valor é JSON tipado no
# ponto de uso (Pydantic/dataclass de quem lê), não um schema por tipo de fato.
memoria = Table(
    "nucleo_memoria",
    metadata,
    # Integer (não BigInteger): no SQLite só INTEGER PRIMARY KEY é alias de rowid
    # e recebe valor automático.
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("modulo", String, nullable=False),
    Column("tipo", String, nullable=False),  # gasto_fixo|meta|preferencia|...
    Column("chave", String, nullable=False),
    Column("valor", String, nullable=False),  # JSON
    Column("atualizado_em", String, nullable=False),
    UniqueConstraint("modulo", "tipo", "chave", name="uq_nucleo_memoria"),
)

# Alertas gerados pelas regras. O histórico de "aceitei/ignorei" é o próprio
# status — não existe tabela separada de recomendações.
insights = Table(
    "nucleo_insights",
    metadata,
    # Integer (não BigInteger): no SQLite só INTEGER PRIMARY KEY é alias de rowid
    # e recebe valor automático.
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("modulo", String, nullable=False),
    Column("regra_id", String, nullable=False),
    Column("chave_dedup", String, nullable=False),
    Column("titulo", String, nullable=False),
    Column("detalhe", String, nullable=False),  # JSON com os números
    Column("severidade", String, nullable=False),  # info|atencao|alerta
    Column("status", String, nullable=False, default="novo"),  # novo|visto|dispensado
    Column("criado_em", String, nullable=False),
    UniqueConstraint("regra_id", "chave_dedup", name="uq_nucleo_insights"),
)
