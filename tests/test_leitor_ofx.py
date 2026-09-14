import re
from datetime import date
from pathlib import Path

import pytest

from personalos.modulos.financas.infra.leitores.ofx import LeitorOFX

FIX = Path(__file__).parent / "fixtures"


def test_le_ofx():
    txs = LeitorOFX().ler(str(FIX / "exemplo.ofx"))
    assert len(txs) == 2
    assert txs[0].fit_id == "OFX-1"
    assert txs[0].valor.centavos == -1234
    assert txs[0].data == date(2026, 6, 1)
    assert txs[0].conta == "12345"


def test_transacao_malformada_gera_erro_claro(tmp_path: Path):
    caminho = tmp_path / "malformado.ofx"
    caminho.write_text(
        "OFXHEADER:100\n"
        "DATA:OFXSGML\n"
        "VERSION:102\n"
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>\n"
        "<CURDEF>BRL<BANKACCTFROM><ACCTID>12345</ACCTID></BANKACCTFROM>\n"
        "<BANKTRANLIST>\n"
        "<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260601<FITID>OFX-1<MEMO>UBER</STMTTRN>\n"
        "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    )
    with pytest.raises(ValueError, match=re.escape(str(caminho))):
        LeitorOFX().ler(str(caminho))
