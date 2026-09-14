import os
from datetime import date
from pathlib import Path

import pytest

from personalos.modulos.financas.infra.leitores.csv_ import LeitorCSV

FIX = Path(__file__).parent / "fixtures"


def test_le_nubank_com_fit_id_real():
    txs = LeitorCSV().ler(str(FIX / "nubank.csv"))
    assert len(txs) == 2
    assert txs[0].fit_id == "abc-111"
    assert txs[0].valor.centavos == -1234
    assert txs[0].data == date(2026, 6, 1)
    assert txs[0].conta == "nubank"


def test_le_generico_gera_fit_id_none():
    txs = LeitorCSV().ler(str(FIX / "generico.csv"))
    assert len(txs) == 2
    assert txs[0].fit_id is None
    assert txs[1].valor.centavos == 300000


def test_linha_malformada_gera_erro_claro():
    with pytest.raises(ValueError, match="linha 3"):
        LeitorCSV().ler(str(FIX / "nubank_linha_ruim.csv"))


def test_arquivo_sem_permissao_gera_erro_claro(tmp_path: Path):
    caminho = tmp_path / "sem_permissao.csv"
    caminho.write_text("Data,Valor,Identificador,Descrição\n2026-06-01,-12.34,abc-111,X\n")
    os.chmod(caminho, 0o000)
    try:
        with pytest.raises(ValueError):
            LeitorCSV().ler(str(caminho))
    finally:
        os.chmod(caminho, 0o644)
