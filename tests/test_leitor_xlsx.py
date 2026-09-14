import re
from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook

from personalos.modulos.financas.infra.leitores.xlsx import LeitorXLSX


def test_le_xlsx(tmp_path: Path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Data", "Valor", "Descricao"])
    ws.append([date(2026, 6, 2), -99.90, "MERCADO"])
    ws.append(["03/06/2026", "1.234,56", "REEMBOLSO"])
    caminho = tmp_path / "e.xlsx"
    wb.save(caminho)

    txs = LeitorXLSX().ler(str(caminho))
    assert len(txs) == 2
    assert txs[0].valor.centavos == -9990
    assert txs[0].data == date(2026, 6, 2)
    assert txs[1].valor.centavos == 123456
    assert txs[1].data == date(2026, 6, 3)
    assert txs[0].fit_id is None


def test_planilha_vazia_gera_erro_claro(tmp_path: Path):
    wb = Workbook()
    caminho = tmp_path / "vazia.xlsx"
    wb.save(caminho)

    with pytest.raises(ValueError, match=re.escape(str(caminho))):
        LeitorXLSX().ler(str(caminho))


def test_celula_malformada_gera_erro_claro(tmp_path: Path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Data", "Valor", "Descricao"])
    ws.append(["nao-e-uma-data", "10.00", "X"])
    caminho = tmp_path / "ruim.xlsx"
    wb.save(caminho)

    with pytest.raises(ValueError, match=f"{re.escape(str(caminho))}, linha 2"):
        LeitorXLSX().ler(str(caminho))


def test_arquivo_corrompido_gera_erro_claro(tmp_path: Path):
    caminho = tmp_path / "corrompido.xlsx"
    caminho.write_bytes(b"isto nao e um arquivo xlsx valido")

    with pytest.raises(ValueError, match=re.escape(str(caminho))):
        LeitorXLSX().ler(str(caminho))
