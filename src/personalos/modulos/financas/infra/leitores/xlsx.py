"""Leitor de extratos XLSX via openpyxl. Cabeçalho flexível (data/valor/descrição)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from openpyxl import load_workbook

from personalos.modulos.financas.aplicacao.portas import TransacaoBruta
from personalos.modulos.financas.dominio.dinheiro import Dinheiro

_COLS_DATA = {"data", "date"}
_COLS_VALOR = {"valor", "amount", "value"}
_COLS_DESC = {"descricao", "descrição", "historico", "histórico", "description", "memo"}


def _norm(s: object) -> str:
    return str(s).strip().lower() if s is not None else ""


def _para_data(v: object) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Data XLSX desconhecida: {v!r}")


def _para_dinheiro(v: object) -> Dinheiro:
    if isinstance(v, (int, float)):
        return Dinheiro.de_decimal(Decimal(str(v)))
    return Dinheiro.de_texto(str(v))


class LeitorXLSX:
    def ler(self, caminho: str) -> list[TransacaoBruta]:
        try:
            wb = load_workbook(caminho, read_only=True, data_only=True)
        except Exception as e:
            raise ValueError(f"{caminho}: {e}") from e
        ws = wb.active
        linhas = ws.iter_rows(values_only=True)
        try:
            cabecalho = [_norm(c) for c in next(linhas)]
        except StopIteration:
            raise ValueError(f"Planilha vazia: {caminho}")
        idx = {nome: i for i, nome in enumerate(cabecalho)}

        def achar(nomes: set[str]) -> int:
            for n in nomes:
                if n in idx:
                    return idx[n]
            raise ValueError(f"Coluna não encontrada ({nomes}) em {caminho}")

        i_data, i_valor = achar(_COLS_DATA), achar(_COLS_VALOR)
        i_desc = next((idx[n] for n in _COLS_DESC if n in idx), None)

        out: list[TransacaoBruta] = []
        for i, row in enumerate(linhas, start=2):  # start=2: linha 1 é o cabeçalho
            if row is None or row[i_data] is None:
                continue
            try:
                desc = str(row[i_desc]).strip() if i_desc is not None and row[i_desc] else ""
                out.append(
                    TransacaoBruta(
                        data=_para_data(row[i_data]),
                        valor=_para_dinheiro(row[i_valor]),
                        descricao=desc,
                        conta="xlsx",
                        fit_id=None,
                    )
                )
            except Exception as e:
                raise ValueError(f"{caminho}, linha {i}: {e}") from e
        wb.close()
        return out
