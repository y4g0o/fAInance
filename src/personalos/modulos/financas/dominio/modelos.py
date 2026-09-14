"""Entidades de domínio (puras). Dinheiro em centavos via Dinheiro."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from personalos.modulos.financas.dominio.dinheiro import Dinheiro


# Nem toda saída de dinheiro é gasto. Transferência entre contas próprias e
# aplicação em investimento MOVEM dinheiro, não o consomem — contá-las como despesa
# infla o custo de vida e faz o sistema recomendar "corte suas aplicações".
# Descoberto nos dados reais: transferências para si mesmo eram a MAIOR "despesa" do
# extrato, e aplicações vinham logo atrás.
#
# A classificação é feita pelas regras de categorização normais (`financas regra`),
# então continua sendo escolha do usuário — o domínio só declara quais categorias
# significam "não é consumo".
CATEGORIAS_NAO_CONSUMO = ("Transferência", "Investimento")


def e_consumo(categoria: str | None) -> bool:
    """Se a transação representa consumo de verdade (e não movimentação própria)."""
    return categoria not in CATEGORIAS_NAO_CONSUMO


@dataclass(frozen=True, slots=True)
class Transacao:
    fit_id: str
    data: date
    valor: Dinheiro
    descricao: str
    conta: str
    categoria: str | None = None


@dataclass(frozen=True, slots=True)
class Regra:
    """Regra determinística de categorização. tipo: 'contem' ou 'regex'."""
    padrao: str
    categoria: str
    tipo: str = "contem"
    prioridade: int = 100

    def __post_init__(self) -> None:
        if self.tipo not in ("contem", "regex"):
            raise ValueError(f"tipo inválido: {self.tipo!r}")
        if not self.padrao.strip():
            raise ValueError("padrao não pode ser vazio")
        if self.tipo == "regex":
            try:
                re.compile(self.padrao)
            except re.error as e:
                raise ValueError(f"regex inválida: {self.padrao!r}") from e
