"""Ports (contratos) da camada de aplicação. Implementados na infra."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Regra, Transacao


@dataclass(frozen=True, slots=True)
class TransacaoBruta:
    """Transação lida de um extrato, antes de categorizar/persistir.
    fit_id None => o caso de uso gera um id sintético estável."""
    data: date
    valor: Dinheiro
    descricao: str
    conta: str
    fit_id: str | None = None


class LeitorExtrato(Protocol):
    def ler(self, caminho: "str") -> list[TransacaoBruta]: ...


class SeletorLeitor(Protocol):
    def __call__(self, caminho: str) -> LeitorExtrato: ...


class RepoTransacoes(Protocol):
    def inserir_muitas(self, transacoes: list[Transacao]) -> int:
        """Insere ignorando fit_id já existente. Retorna nº de novas."""
        ...

    def listar(
        self, inicio: date | None = None, fim: date | None = None
    ) -> list[Transacao]: ...

    def definir_categoria(self, fit_ids: list[str], categoria: str | None) -> int:
        """Só a categoria muda; devolve quantas linhas mudaram de fato."""
        ...


class RepoRegras(Protocol):
    def listar(self) -> list[Regra]: ...

    def adicionar(self, regra: Regra) -> bool: ...

    def remover(self, padrao: str, tipo: str = "contem") -> int: ...
