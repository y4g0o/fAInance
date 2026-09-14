"""Leitor de extratos CSV. Detecta o banco pelo cabeçalho (portado do importar.py)."""
from __future__ import annotations

import csv
from datetime import date, datetime
from typing import TypedDict

from personalos.modulos.financas.aplicacao.portas import TransacaoBruta
from personalos.modulos.financas.dominio.dinheiro import Dinheiro


class _Mapeamento(TypedDict):
    detectar: list[str]
    data: str
    valor: str
    fit_id: str | None
    descricao: str
    conta: str


MAPEAMENTOS: list[_Mapeamento] = [
    {
        "detectar": ["Data", "Valor", "Identificador", "Descrição"],
        "data": "Data", "valor": "Valor", "fit_id": "Identificador",
        "descricao": "Descrição", "conta": "nubank",
    },
    {
        "detectar": ["Data", "Historico", "Valor"],
        "data": "Data", "valor": "Valor", "fit_id": None,
        "descricao": "Historico", "conta": "banco",
    },
    {
        "detectar": ["date", "description", "amount"],
        "data": "date", "valor": "amount", "fit_id": None,
        "descricao": "description", "conta": "conta",
    },
]


def _parse_data(s: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Data desconhecida: {s!r}")


def _detectar(cabecalho: list[str]) -> _Mapeamento | None:
    for m in MAPEAMENTOS:
        if all(c in cabecalho for c in m["detectar"]):
            return m
    return None


class LeitorCSV:
    def ler(self, caminho: str) -> list[TransacaoBruta]:
        try:
            with open(caminho, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                mapa = _detectar(list(reader.fieldnames or []))
                if not mapa:
                    raise ValueError(f"CSV não reconhecido: {caminho}")
                out: list[TransacaoBruta] = []
                for i, row in enumerate(reader, start=2):  # start=2: linha 1 é o cabeçalho
                    try:
                        col_fit = mapa["fit_id"]
                        fit = (row.get(col_fit) or "").strip() or None
                        out.append(
                            TransacaoBruta(
                                data=_parse_data(row[mapa["data"]] or ""),
                                valor=Dinheiro.de_texto(row[mapa["valor"]] or ""),
                                descricao=(row.get(mapa["descricao"]) or "").strip(),
                                conta=mapa["conta"],
                                fit_id=fit,
                            )
                        )
                    except (AttributeError, ValueError, KeyError) as e:
                        raise ValueError(f"{caminho}, linha {i}: {e}") from e
                return out
        except OSError as e:
            raise ValueError(f"{caminho}: {e}") from e
