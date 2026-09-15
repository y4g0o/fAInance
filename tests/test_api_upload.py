"""Upload de extrato: arrastar o arquivo na tela em vez de copiar pra uma pasta.

Guardas testadas aqui são de segurança, não de conveniência: o arquivo vem de
fora e é gravado em disco, então nome, extensão e tamanho são superfície de
ataque — mesmo num sistema de um usuário só.
"""
from pathlib import Path

import pytest

from personalos.api.app import criar_app

from .apoio import cliente_navegador

OFX_MINIMO = b"""OFXHEADER:100
DATA:OFXSGML

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>BRL<BANKACCTFROM><ACCTID>123<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260801<TRNAMT>-50.00<FITID>up1<MEMO>MERCADO</STMTTRN>
</BANKTRANLIST>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


@pytest.fixture
def cliente(tmp_path: Path, monkeypatch):
    """Extratos vão pra um diretório temporário — nenhum teste escreve no seu disco."""
    destino = tmp_path / "extratos"
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dados"))
    monkeypatch.setattr(
        "personalos.modulos.financas.api.diretorio_extratos", lambda: destino
    )
    return cliente_navegador(criar_app(db=tmp_path / "up.db")), destino


def test_upload_de_ofx_importa_as_transacoes(cliente):
    api, _ = cliente

    r = api.post(
        "/api/financas/extratos",
        files={"arquivos": ("extrato.ofx", OFX_MINIMO, "application/octet-stream")},
    )

    assert r.status_code == 201
    assert r.json()["novas"] == 1


def test_upload_da_mesma_coisa_duas_vezes_nao_duplica(cliente):
    """Dedup por fit_id: reenviar o mesmo extrato é seguro e é o caso comum de
    quem baixa 'últimos 90 dias' todo mês."""
    api, _ = cliente
    arquivo = {"arquivos": ("extrato.ofx", OFX_MINIMO, "application/octet-stream")}

    api.post("/api/financas/extratos", files=arquivo)
    segundo = api.post("/api/financas/extratos", files=arquivo)

    assert segundo.json()["novas"] == 0


def test_extensao_fora_da_lista_e_recusada(cliente):
    api, destino = cliente

    r = api.post(
        "/api/financas/extratos",
        files={"arquivos": ("virus.sh", b"rm -rf /", "application/octet-stream")},
    )

    assert r.status_code == 415
    assert not list(destino.glob("*.sh"))


def test_nome_com_travessia_de_caminho_nao_escapa_do_diretorio(cliente):
    """'../../.bashrc.ofx' não pode gravar fora da pasta de extratos."""
    api, destino = cliente

    api.post(
        "/api/financas/extratos",
        files={"arquivos": ("../../escapou.ofx", OFX_MINIMO, "application/octet-stream")},
    )

    assert not (destino.parent.parent / "escapou.ofx").exists()
    assert list(destino.glob("*.ofx"))


def test_arquivo_grande_demais_e_recusado(cliente):
    api, _ = cliente

    r = api.post(
        "/api/financas/extratos",
        files={"arquivos": ("gigante.ofx", b"x" * (11 * 1024 * 1024), "application/octet-stream")},
    )

    assert r.status_code == 413


def test_pdf_que_nao_reconcilia_e_recusado_e_nao_fica_no_disco(cliente, tmp_path):
    """Guarda que mais importa no PDF: se a soma não bate com os saldos do próprio
    extrato, o arquivo é recusado. E não pode sobrar em disco — extrato que não
    pôde ser lido só acumula confusão na pasta."""
    from .pdf_sintetico import escrever_pdf
    from .test_leitor_pdf import EXTRATO_COERENTE

    api, destino = cliente
    faltando = [linha for linha in EXTRATO_COERENTE if "SALARIO" not in linha]
    arquivo = escrever_pdf(tmp_path / "quebrado.pdf", faltando)

    r = api.post(
        "/api/financas/extratos",
        files={"arquivos": ("quebrado.pdf", arquivo.read_bytes(), "application/pdf")},
    )

    assert r.status_code == 422
    assert not list(destino.glob("*.pdf"))


def test_upload_regenera_os_alertas_como_a_cli_faz(cliente, monkeypatch):
    """Paridade: `financas importar` aprende gastos fixos e gera insights ao fim.
    Se a tela não fizer o mesmo, quem usa a interface para de receber alerta —
    e não tem como perceber que parou."""
    chamou = []
    import personalos.modulos.financas.api as modulo_api

    monkeypatch.setattr(modulo_api, "reprocessar_insights", lambda engine: chamou.append(engine))
    api, _ = cliente

    api.post(
        "/api/financas/extratos",
        files={"arquivos": ("extrato.ofx", OFX_MINIMO, "application/octet-stream")},
    )

    assert len(chamou) == 1, "importar pela tela não regenerou os alertas"


def test_extrato_gravado_nao_fica_legivel_por_outros(cliente):
    """Extrato bancário com permissão 644 é legível por qualquer usuário local.
    O banco e os backups já eram 600; a pasta de extratos nasceu com o umask
    padrão e ficou 775 — achado na revisão de segurança."""
    api, destino = cliente

    api.post(
        "/api/financas/extratos",
        files={"arquivos": ("extrato.ofx", OFX_MINIMO, "application/octet-stream")},
    )

    assert destino.stat().st_mode & 0o077 == 0, "pasta de extratos acessível a outros"
    for arquivo in destino.glob("*.ofx"):
        assert arquivo.stat().st_mode & 0o077 == 0, f"{arquivo.name} legível por outros"


def test_arquivo_de_mesmo_nome_e_conteudo_diferente_nao_apaga_o_anterior(cliente):
    """Os extratos originais são a recuperação de desastre. Sobrescrever em
    silêncio um arquivo de mesmo nome apagaria a cópia boa."""
    api, destino = cliente
    outro = OFX_MINIMO.replace(b"up1", b"up2").replace(b"-50.00", b"-70.00")

    api.post("/api/financas/extratos", files={"arquivos": ("extrato.ofx", OFX_MINIMO, "application/octet-stream")})
    api.post("/api/financas/extratos", files={"arquivos": ("extrato.ofx", outro, "application/octet-stream")})

    guardados = sorted(p.read_bytes() for p in destino.glob("*.ofx"))
    assert len(guardados) == 2, "o segundo envio apagou o primeiro"
