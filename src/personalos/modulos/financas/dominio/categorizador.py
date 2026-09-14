"""Categorização determinística por regras. Sem IA."""
from __future__ import annotations

import re

from personalos.modulos.financas.dominio.modelos import Regra, Transacao


def categorizar(t: Transacao, regras: list[Regra]) -> str | None:
    """Primeira regra (por prioridade crescente) que casa vence. Sem match -> None."""
    alvo = t.descricao.lower()
    for regra in sorted(regras, key=lambda r: r.prioridade):
        if regra.tipo == "regex":
            if re.search(regra.padrao, t.descricao, re.IGNORECASE):
                return regra.categoria
        elif regra.padrao.lower() in alvo:
            return regra.categoria
    return None
