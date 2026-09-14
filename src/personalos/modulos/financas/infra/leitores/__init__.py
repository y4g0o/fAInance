"""Seleção de leitor por extensão do arquivo."""
from __future__ import annotations

from pathlib import Path

from personalos.modulos.financas.aplicacao.portas import LeitorExtrato
from personalos.modulos.financas.infra.leitores.csv_ import LeitorCSV
from personalos.modulos.financas.infra.leitores.ofx import LeitorOFX
from personalos.modulos.financas.infra.leitores.pdf import LeitorPDF
from personalos.modulos.financas.infra.leitores.xlsx import LeitorXLSX


def detectar_leitor(caminho: str) -> LeitorExtrato:
    ext = Path(caminho).suffix.lower()
    if ext == ".csv":
        return LeitorCSV()
    if ext in (".ofx", ".qfx"):
        return LeitorOFX()
    if ext == ".pdf":
        return LeitorPDF()
    if ext == ".xlsx":
        return LeitorXLSX()
    raise ValueError(f"Extensão não suportada: {ext}")
