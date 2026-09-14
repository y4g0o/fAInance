"""Leitor de extrato em PDF — o formato mais frágil, com as guardas mais duras.

Todas as asserções de mascaramento foram conferidas rodando o código, não contadas
de cabeça.
"""
from datetime import date

import pytest
from typer.testing import CliRunner

from personalos.modulos.financas.infra.leitores.pdf import (
    VALOR,
    _para_centavos,
    _para_data,
    _paginas,
    diagnosticar,
    LeitorPDF,
    e_candidata,
    linhas_de_texto,
    mascarar,
)
from personalos.modulos.financas.cli import app
from tests.pdf_sintetico import EXTRATO, escrever_pdf

runner = CliRunner()

# ---------- mascaramento: o que permite calibrar sem ler o extrato de ninguém ----------


def test_mascarar_esconde_conteudo_e_preserva_layout():
    assert mascarar("DELIVERIA *PEDIDO 05/03/2026 -89,90") == "aaaaaaaaa *aaaaaa 99/99/9999 -99,99"
    assert mascarar("Saldo anterior 1.234,56") == "aaaaa aaaaaaaa 9.999,99"


def test_mascarar_cobre_letra_acentuada():
    # 'ê' é word char em unicode e vira 'a'. "Transferência" tem 13 letras.
    assert mascarar("Transferência recebida") == "aaaaaaaaaaaaa aaaaaaaa"


def test_mascarar_nao_deixa_passar_digito():
    mascarado = mascarar("PIX ENVIADO JOAO 12345678900 07/03/2026 -1.500,00")
    assert not any(c.isdigit() and c != "9" for c in mascarado)
    assert "JOAO" not in mascarado


# ---------- valores: as notações que extrato brasileiro usa ----------


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("1.234,56", 123456),
        ("-1.234,56", -123456),
        ("1.234,56-", -123456),  # sinal à direita (padrão de alguns bancos)
        ("(1.234,56)", -123456),  # notação contábil
        ("R$ 89,90", 8990),
        ("0,01", 1),
        ("12.345.678,90", 1234567890),
    ],
)
def test_para_centavos_cobre_as_notacoes_de_extrato(bruto, esperado):
    assert _para_centavos(bruto) == esperado


def test_valor_acha_transacao_E_saldo_na_mesma_linha():
    """Extrato com coluna de saldo devolve DOIS números na mesma linha.

    É por isso que o perfil do banco precisa dizer qual coluna é a transação: sem
    isso, um extrato com saldo corrente seria lido com o valor errado, em silêncio.
    """
    assert VALOR.findall("05/03/2026 MERCADO -89,90 1.234,56") == ["-89,90", "1.234,56"]


# ---------- datas ----------


def test_para_data_aceita_os_tres_formatos():
    assert _para_data("05/03/2026", None) == date(2026, 3, 5)
    assert _para_data("05/03/26", None) == date(2026, 3, 5)
    assert _para_data("05/03", 2026) == date(2026, 3, 5)


def test_para_data_sem_ano_e_sem_referencia_falha_alto():
    with pytest.raises(ValueError, match="sem ano"):
        _para_data("05/03", None)


def test_para_data_impossivel_falha(_=None):
    with pytest.raises(ValueError):
        _para_data("99/99/2026", None)


# ---------- linha candidata: base da guarda contra falha silenciosa ----------


def test_e_candidata_exige_data_E_valor():
    assert e_candidata("05/03/2026 MERCADO -89,90")
    assert not e_candidata("05/03/2026 MERCADO")  # sem valor
    assert not e_candidata("MERCADO -89,90")  # sem data
    assert not e_candidata("Extrato de conta corrente")  # nenhum dos dois
    assert not e_candidata("")


# ---------- integração real com o pdfplumber (PDF de verdade, conteúdo sintético) ----------


def test_le_linhas_de_um_pdf_de_verdade(tmp_path):
    arquivo = escrever_pdf(tmp_path / "e.pdf", EXTRATO)
    linhas = linhas_de_texto(str(arquivo))
    assert linhas == EXTRATO
    assert _paginas(str(arquivo)) == 1


def test_diagnostico_conta_candidatas_e_mascara_as_amostras(tmp_path):
    arquivo = escrever_pdf(tmp_path / "e.pdf", EXTRATO)
    d = diagnosticar(str(arquivo))
    assert d.paginas == 1
    assert d.linhas == len(EXTRATO)
    assert d.candidatas == 2  # as duas linhas de transação
    assert d.valores_por_candidata == (1, 1)
    # nenhuma amostra pode conter conteúdo real
    juntas = " ".join(d.amostras_mascaradas + d.amostras_de_total)
    for segredo in ("MERCADO", "SALARIO", "Saldo", "1.000", "5.910", "89,90"):
        assert segredo not in juntas
    assert "99/99/9999" in juntas  # mas o layout aparece


def test_diagnostico_encontra_as_linhas_de_total(tmp_path):
    arquivo = escrever_pdf(tmp_path / "e.pdf", EXTRATO)
    d = diagnosticar(str(arquivo))
    assert len(d.amostras_de_total) == 2  # 'Saldo anterior' e 'Saldo final'


def test_diagnostico_de_pdf_sem_texto_nao_quebra(tmp_path):
    arquivo = escrever_pdf(tmp_path / "vazio.pdf", [])
    d = diagnosticar(str(arquivo))
    assert d.linhas == 0 and d.candidatas == 0
    assert d.amostras_mascaradas == ()


# ---------- comando de diagnóstico ----------


def test_comando_inspecionar_pdf_nao_imprime_conteudo(tmp_path):
    arquivo = escrever_pdf(tmp_path / "e.pdf", EXTRATO)
    resultado = runner.invoke(app, ["inspecionar-pdf", str(arquivo)])
    assert resultado.exit_code == 0
    saida = resultado.stdout
    assert "candidatas: 2" in saida
    for segredo in ("MERCADO", "SALARIO", "89,90", "5.910"):
        assert segredo not in saida
    assert "99/99/9999" in saida


def test_comando_inspecionar_pdf_avisa_quando_parece_escaneado(tmp_path):
    arquivo = escrever_pdf(tmp_path / "img.pdf", ["Banco Sintetico", "Extrato"])
    saida = runner.invoke(app, ["inspecionar-pdf", str(arquivo)]).stdout
    assert "escaneado" in saida and "OCR" in saida


def test_comando_inspecionar_pdf_arquivo_inexistente(tmp_path):
    resultado = runner.invoke(app, ["inspecionar-pdf", str(tmp_path / "nao_existe.pdf")])
    assert resultado.exit_code == 1
    assert "não encontrado" in resultado.stdout


def test_comando_inspecionar_pdf_arquivo_corrompido_nao_da_traceback(tmp_path):
    ruim = tmp_path / "ruim.pdf"
    ruim.write_bytes(b"isto nao e um PDF")
    resultado = runner.invoke(app, ["inspecionar-pdf", str(ruim)])
    assert resultado.exit_code == 1
    assert "Não foi possível ler o PDF" in resultado.stdout
    assert "Traceback" not in resultado.stdout


# ---------- leitor: as duas guardas ----------

# Extrato que FECHA: saldo 1000 no dia 01; -100 e +500 no dia 05; saldo 1400 no 05.
EXTRATO_COERENTE = [
    "Banco Sintetico - Extrato",
    "01/03/2026 Saldo do dia 1.000,00",
    "05/03/2026 MERCADO BOM PRECO -100,00",
    "05/03/2026 SALARIO 500,00",
    "05/03/2026 Saldo do dia 1.400,00",
]


def test_ler_ignora_linhas_de_saldo_e_devolve_so_movimento(tmp_path):
    """~30% das linhas candidatas dos extratos reais eram 'Saldo do dia'.
    Importá-las criaria transações fantasmas."""
    arquivo = escrever_pdf(tmp_path / "e.pdf", EXTRATO_COERENTE)
    brutas = LeitorPDF().ler(str(arquivo))
    assert [b.valor.centavos for b in brutas] == [-10000, 50000]
    assert all("Saldo" not in b.descricao for b in brutas)
    assert brutas[0].descricao == "MERCADO BOM PRECO"
    assert brutas[0].fit_id is None  # dedup fica com o caso de uso já testado


def test_reconciliacao_aprova_extrato_coerente(tmp_path):
    arquivo = escrever_pdf(tmp_path / "e.pdf", EXTRATO_COERENTE)
    r = LeitorPDF().reconciliar(str(arquivo))
    assert r is not None and r.segmentos == 1 and r.fecham == 1 and r.confiavel


def test_ler_FALHA_quando_a_soma_nao_bate_com_o_saldo(tmp_path):
    """A guarda que importa: falta uma transação, o saldo não fecha, e o leitor
    recusa em vez de gravar número errado em silêncio."""
    faltando = [linha for linha in EXTRATO_COERENTE if "SALARIO" not in linha]
    arquivo = escrever_pdf(tmp_path / "e.pdf", faltando)
    with pytest.raises(ValueError, match="não fecha com o saldo"):
        LeitorPDF().ler(str(arquivo))


def test_erro_de_reconciliacao_nao_vaza_conteudo_do_extrato(tmp_path):
    faltando = [linha for linha in EXTRATO_COERENTE if "SALARIO" not in linha]
    arquivo = escrever_pdf(tmp_path / "e.pdf", faltando)
    with pytest.raises(ValueError) as erro:
        LeitorPDF().ler(str(arquivo))
    texto = str(erro.value)
    for segredo in ("MERCADO", "BOM PRECO", "1.000", "1.400", "100,00"):
        assert segredo not in texto


def test_ler_FALHA_em_linha_ambigua_com_dois_valores(tmp_path):
    """Extrato com coluna de saldo corrente traz dois números por linha: adivinhar
    qual é a transação é como se produz erro silencioso."""
    arquivo = escrever_pdf(
        tmp_path / "e.pdf",
        ["01/03/2026 Saldo do dia 1.000,00", "05/03/2026 MERCADO -100,00 900,00"],
    )
    with pytest.raises(ValueError, match="2 valores"):
        LeitorPDF().ler(str(arquivo))


def test_reconciliacao_tolera_falha_apenas_no_ultimo_segmento(tmp_path):
    """Nos três extratos reais, só o último segmento falhava — a última linha de
    saldo costuma ser o saldo atual, não o fechamento do dia."""
    com_ultimo_torto = EXTRATO_COERENTE + [
        "09/03/2026 PADARIA -50,00",
        "09/03/2026 Saldo do dia 9.999,00",  # não bate de propósito
    ]
    arquivo = escrever_pdf(tmp_path / "e.pdf", com_ultimo_torto)
    r = LeitorPDF().reconciliar(str(arquivo))
    assert r is not None and r.segmentos == 2 and r.fecham == 1
    assert r.ultimo_falhou and r.confiavel
    assert len(LeitorPDF().ler(str(arquivo))) == 3  # não levanta


def test_reconciliacao_indeterminada_quando_nao_ha_saldo(tmp_path):
    """Sem saldo declarado não dá para conferir — indeterminado não é reprovado."""
    arquivo = escrever_pdf(tmp_path / "e.pdf", ["05/03/2026 MERCADO -100,00"])
    assert LeitorPDF().reconciliar(str(arquivo)) is None
    assert len(LeitorPDF().ler(str(arquivo))) == 1


def test_pdf_e_reconhecido_pelo_seletor_de_leitor(tmp_path):
    from personalos.modulos.financas.infra.leitores import detectar_leitor

    assert isinstance(detectar_leitor("x.pdf"), LeitorPDF)
