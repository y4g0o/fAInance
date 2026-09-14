"""Gera um PDF mínimo válido, com texto, sem dependência nova.

Existe para que o caminho de leitura de PDF tenha teste de INTEGRAÇÃO real — com
monkeypatch em `linhas_de_texto` a gente testaria a própria suposição, não o
pdfplumber. Conteúdo é sempre sintético: nenhum extrato de verdade entra em teste.
"""
from __future__ import annotations

import io
from pathlib import Path


def escrever_pdf(destino: Path, linhas: list[str]) -> Path:
    texto = (
        "BT /F1 10 Tf 40 750 Td 12 TL\n"
        + "\n".join(f"({linha}) Tj T*" for linha in linhas)
        + "\nET"
    )
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(texto)} >>\nstream\n{texto}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    posicoes = []
    for numero, objeto in enumerate(objetos, 1):
        posicoes.append(buffer.tell())
        buffer.write(f"{numero} 0 obj\n{objeto}\nendobj\n".encode("latin-1"))
    inicio_xref = buffer.tell()
    buffer.write(f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode())
    for posicao in posicoes:
        buffer.write(f"{posicao:010d} 00000 n \n".encode())
    buffer.write(
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{inicio_xref}\n%%EOF\n".encode()
    )
    destino.write_bytes(buffer.getvalue())
    return destino


# Extrato sintético com as três formas que importam: cabeçalho sem valor, linhas de
# transação, e linhas de saldo (que a reconciliação vai usar).
EXTRATO = [
    "Banco Sintetico - Extrato de conta corrente",
    "Periodo: 01/03/2026 a 31/03/2026",
    "Saldo anterior 1.000,00",
    "05/03/2026 MERCADO BOM PRECO -89,90",
    "07/03/2026 SALARIO 5.000,00",
    "Saldo final 5.910,10",
]
