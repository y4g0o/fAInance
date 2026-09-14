"""Porta de conversa em linguagem natural.

Mora no kernel porque o painel importa **só isto** — não o consultor. Trocar a
implementação (modelo local, outro runtime, ou nada) não toca no painel.

O contrato é deliberadamente RICO desde o começo: `numeros` e `ferramentas` são o
que torna uma resposta financeira auditável ("de onde veio esse número?"), e é o
painel que os renderiza. Um contrato mínimo obrigaria a mudança quebrar o painel
quando o consultor chegasse.

Regra que atravessa tudo: **nenhum campo aqui é preenchido por LLM**. `numeros` e
`ferramentas` são montados pelo código a partir das funções que rodaram — ver
ADR 0002.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ChatIndisponivel(RuntimeError):
    """Não há serviço de conversa configurado, ou ele não pôde responder."""


@dataclass(frozen=True)
class NumeroCitado:
    """Um número que apareceu na resposta, com a função que o produziu."""

    rotulo: str
    formatado: str
    fonte: str  # "custo_basico(hoje=2026-08-05)" — função e argumentos


@dataclass(frozen=True)
class Sugestao:
    texto: str
    origem: str  # ferramenta que embasou a sugestão
    insight_id: int | None = None  # obrigatório quando vem de nucleo_insights


@dataclass(frozen=True)
class Resposta:
    texto: str
    numeros: tuple[NumeroCitado, ...] = ()
    sugestoes: tuple[Sugestao, ...] = ()
    ferramentas: tuple[str, ...] = ()
    modelo: str | None = None
    degradado: bool = False  # respondeu sem LLM, ou com menos do que devia
    motivo: str | None = None  # por que degradou, em linguagem de gente
    duracao_ms: int = 0


@dataclass(frozen=True)
class Pergunta:
    texto: str
    modulo: str | None = None  # dica de escopo, quando a interface souber
    contexto: dict[str, str] = field(default_factory=dict)


class ServicoChat(Protocol):
    def responder(self, pergunta: Pergunta) -> Resposta:
        """Nunca levanta: toda falha vira Resposta com degradado=True."""
        ...
