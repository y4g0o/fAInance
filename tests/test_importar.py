from datetime import date
from pathlib import Path

from personalos.modulos.financas.aplicacao.importar import fit_id_estavel, importar_extratos
from personalos.modulos.financas.aplicacao.portas import TransacaoBruta
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Regra
from personalos.modulos.financas.infra.leitores import detectar_leitor

FIX = Path(__file__).parent / "fixtures"


def _bruta(desc: str, cents: int, dia: int = 1, fit=None) -> TransacaoBruta:
    return TransacaoBruta(date(2026, 6, dia), Dinheiro(cents), desc, "nubank", fit)


def test_fit_id_estavel_e_deterministico():
    a = fit_id_estavel(_bruta("café", -500), 0)
    b = fit_id_estavel(_bruta("café", -500), 0)
    assert a == b and len(a) == 40  # sha1 hex


def test_fit_id_diferencia_ocorrencias():
    assert fit_id_estavel(_bruta("café", -500), 0) != fit_id_estavel(_bruta("café", -500), 1)


def test_importa_aplica_regras_e_dedup(repo_transacoes, repo_regras):
    repo_regras.adicionar(Regra("uber", "Transporte"))
    n1 = importar_extratos([str(FIX / "nubank.csv")], repo_transacoes, repo_regras, detectar_leitor)
    assert n1 == 2
    txs = {t.descricao: t for t in repo_transacoes.listar()}
    assert txs["UBER TRIP"].categoria == "Transporte"
    assert txs["DELIVERIA PEDIDO"].categoria is None
    # reimportar o mesmo arquivo é idempotente
    n2 = importar_extratos([str(FIX / "nubank.csv")], repo_transacoes, repo_regras, detectar_leitor)
    assert n2 == 0


def test_importa_gera_fit_id_para_fonte_sem_id(repo_transacoes, repo_regras):
    n = importar_extratos([str(FIX / "generico.csv")], repo_transacoes, repo_regras, detectar_leitor)
    assert n == 2
    assert all(len(t.fit_id) == 40 for t in repo_transacoes.listar())


def test_arquivos_com_conteudo_identico_nao_duplicam(tmp_path, repo_transacoes, repo_regras):
    """Dois arquivos com o mesmo conteúdo são o mesmo extrato, não o dobro de gastos.

    Este teste já existiu afirmando o contrário (esperava 4 linhas). Estava
    codificando a limitação que o docstring de fit_id_estavel registrava, e que os
    extratos reais do usuário expuseram: PDFs do mesmo banco cobrem períodos
    sobrepostos, então a mesma transação chega por dois arquivos na mesma execução.
    Contar em dobro é pior que recusar.
    """
    conteudo = "date,description,amount\n2026-06-10,CAFE,-5.00\n2026-06-10,CAFE,-5.00\n"
    arquivo_a = tmp_path / "a.csv"
    arquivo_b = tmp_path / "b.csv"
    arquivo_a.write_text(conteudo)
    arquivo_b.write_text(conteudo)
    n = importar_extratos([str(arquivo_a), str(arquivo_b)], repo_transacoes, repo_regras, detectar_leitor)
    assert n == 2  # os dois cafés de verdade, uma vez cada
    assert len({t.fit_id for t in repo_transacoes.listar()}) == 2


# ---------- extratos sobrepostos da MESMA conta (caso real: PDFs mensais) ----------


class _LeitorFake:
    """Leitor que devolve o que lhe deram, para simular arquivos sobrepostos."""

    def __init__(self, por_caminho: dict[str, list[TransacaoBruta]]) -> None:
        self._por_caminho = por_caminho

    def __call__(self, caminho: str) -> "_LeitorFake":
        self._atual = caminho
        return self

    def ler(self, caminho: str) -> list[TransacaoBruta]:
        return self._por_caminho[caminho]


def test_transacao_repetida_em_extratos_sobrepostos_entra_uma_vez(
    repo_transacoes, repo_regras
):
    """Extratos de PDF do mesmo banco se sobrepõem: 'últimos 90 dias' baixado três
    vezes cobre os mesmos meses. A mesma transação vinda de dois arquivos na MESMA
    execução não pode virar duas linhas — seria gasto contado em dobro."""
    comum = _bruta("MERCADO", -8990, dia=5)
    leitor = _LeitorFake({"a.pdf": [comum], "b.pdf": [comum]})
    n = importar_extratos(["a.pdf", "b.pdf"], repo_transacoes, repo_regras, leitor)
    assert n == 1
    assert len(repo_transacoes.listar()) == 1


def test_duplicata_legitima_dentro_do_mesmo_arquivo_e_preservada(
    repo_transacoes, repo_regras
):
    """Dois cafés iguais no mesmo dia são dois gastos de verdade, e o extrato os
    lista duas vezes. O dedup não pode comê-los."""
    cafe = _bruta("CAFE", -500, dia=5)
    leitor = _LeitorFake({"a.pdf": [cafe, cafe]})
    n = importar_extratos(["a.pdf"], repo_transacoes, repo_regras, leitor)
    assert n == 2
    assert len(repo_transacoes.listar()) == 2


def test_sobreposicao_preserva_a_contagem_de_duplicatas_legitimas(
    repo_transacoes, repo_regras
):
    """O caso difícil: dois cafés iguais aparecem nos DOIS arquivos sobrepostos.
    O resultado certo é dois, não um e não quatro."""
    cafe = _bruta("CAFE", -500, dia=5)
    leitor = _LeitorFake({"a.pdf": [cafe, cafe], "b.pdf": [cafe, cafe]})
    n = importar_extratos(["a.pdf", "b.pdf"], repo_transacoes, repo_regras, leitor)
    assert n == 2
    assert len(repo_transacoes.listar()) == 2
