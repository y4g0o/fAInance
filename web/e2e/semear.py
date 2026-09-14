"""Semeia o banco descartável do teste de ponta a ponta.

Dados fictícios: o teste precisa de grupos repetidos e sem categoria, que é a
situação que a tela de categorizar existe para resolver.
"""
import sys
from datetime import date
from pathlib import Path

from personalos.api.app import criar_app
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoContasSQL, RepoTransacoesSQL

destino = Path(sys.argv[1])
app = criar_app(db=destino)
RepoTransacoesSQL(app.state.engine).inserir_muitas(
    [
        Transacao(f"d{i}", date(2026, 8, i + 1), Dinheiro(-2800 - i * 310),
                  "PIX QRS DELIVERIA BR", "conta")
        for i in range(10)
    ]
    + [
        Transacao(f"t{i}", date(2026, 8, i + 1), Dinheiro(-5611),
                  "PIX QRS TELECOMIX", "conta")
        for i in range(9)
    ]
)
RepoContasSQL(app.state.engine).definir_saldo_inicial("conta", Dinheiro(180000))
print(f"semeado: {destino}")
