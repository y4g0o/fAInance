"""Entidades de domínio (puras). Dinheiro em centavos via Dinheiro."""
from __future__ import annotations

import re
from collections.abc import Collection, Mapping
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


def e_consumo(
    categoria: str | None,
    nao_consumo: Collection[str] | Mapping[str, date | None] = (),
    quando: date | None = None,
) -> bool:
    """Se a transação representa consumo de verdade (e não movimentação própria).

    `nao_consumo` são as categorias que o USUÁRIO declarou como movimentação. A
    lista fixa acima é só o padrão: o nome que o banco dá para transferência
    própria varia ("Conta de uso", "Movimentação"), e o código não tem como
    adivinhar. Quem sabe o que cada categoria significa é quem vive com elas.

    Cada declaração pode ter **data de início**, e ela existe por um caso real:
    a transferência para outra conta só deixa de ser gasto no mês em que essa
    conta passa a ser importada. Antes disso a transferência é a única pista do
    gasto, e neutralizá-la apagaria despesa de verdade do histórico.
    """
    if categoria in CATEGORIAS_NAO_CONSUMO:
        return False
    if categoria is None or categoria not in nao_consumo:
        return True
    inicio = nao_consumo.get(categoria) if isinstance(nao_consumo, Mapping) else None
    if inicio is None:
        return False
    return quando is not None and quando < inicio


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
