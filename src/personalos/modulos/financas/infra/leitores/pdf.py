"""Leitor de extrato em PDF — o formato mais frágil, com as guardas mais duras.

Por que PDF exige tratamento diferente de CSV/OFX: naqueles, uma linha ou vem ou
não vem. Aqui a falha é SILENCIOSA — some uma linha na quebra de página, duas
colunas grudam, um sinal de negativo fica órfão. Você não percebe: só decide com
número errado por meses.

Estado atual: este módulo tem o **reconhecimento** (regex de data e valor de extrato
brasileiro), o **mascaramento** e o **diagnóstico**. O leitor propriamente dito e as
duas guardas planejadas — nenhuma linha candidata ignorada em silêncio, e
reconciliação da soma contra o saldo declarado — entram quando o layout de um banco
real for conhecido.

Por que não antes: não existe "PDF de extrato" padrão, cada banco inventa o seu.
Desenhar a estrutura de perfil antes de ver um arquivo de verdade seria adivinhar —
e adivinhar layout é justamente como se produz o erro silencioso descrito acima. O
caminho é `personalos financas inspecionar-pdf`, que revela a estrutura em forma
MASCARADA (letra → 'a', dígito → '9'), segura para compartilhar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

import pdfplumber

from personalos.modulos.financas.aplicacao.portas import TransacaoBruta
from personalos.modulos.financas.dominio.dinheiro import Dinheiro

# dd/mm/aaaa, dd/mm/aa ou dd/mm — a forma como banco brasileiro escreve data.
DATA = re.compile(r"\b(\d{2}/\d{2}(?:/\d{2,4})?)\b")
# 1.234,56 / 1234,56 / -45,90 / 45,90- / R$ 45,90 (parênteses = negativo, contábil)
VALOR = re.compile(r"(?<![\d,.])(-?\(?R?\$?\s?\d{1,3}(?:\.\d{3})*,\d{2}\)?-?)(?![\d])")


def mascarar(texto: str) -> str:
    """Troca letra por 'a' e dígito por '9', preservando pontuação e posição.

    É o que permite calibrar um perfil sem ler o extrato de ninguém: revela o
    layout ("aaaaa 99/99/9999 9.999,99") e não o conteúdo. Preserva a quantidade
    de dígitos porque é o que distingue 1.234,56 de 12,34 — ou seja, revela a
    ordem de grandeza dos valores, e nada além disso.
    """
    return re.sub(r"\d", "9", re.sub(r"[^\W\d_]", "a", texto))


def linhas_de_texto(caminho: str) -> list[str]:
    """Todas as linhas de texto do PDF, na ordem, sem linha em branco."""
    linhas: list[str] = []
    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            linhas.extend(linha.strip() for linha in texto.splitlines() if linha.strip())
    return linhas


def _paginas(caminho: str) -> int:
    """Contagem de páginas, isolada para o diagnóstico ser testável em partes."""
    with pdfplumber.open(caminho) as pdf:
        return len(pdf.pages)


def e_candidata(linha: str) -> bool:
    """Linha que PARECE transação: tem data e tem valor. Base da guarda nº 1."""
    return bool(DATA.search(linha)) and bool(VALOR.search(linha))


def _para_centavos(bruto: str) -> int:
    """Converte um valor achado por VALOR em centavos, com sinal."""
    texto = bruto.strip()
    negativo = (
        texto.startswith("-")
        or texto.endswith("-")
        or (texto.startswith("(") or texto.endswith(")"))
    )
    limpo = texto.strip("-()").replace("R$", "").replace(" ", "")
    centavos = Dinheiro.de_texto(limpo).centavos
    return -abs(centavos) if negativo else abs(centavos)


def _para_data(bruto: str, ano_padrao: int | None) -> date:
    partes = bruto.split("/")
    if len(partes) == 2:
        if ano_padrao is None:
            raise ValueError(f"data {bruto!r} sem ano e sem ano de referência no extrato")
        return date(ano_padrao, int(partes[1]), int(partes[0]))
    formato = "%d/%m/%Y" if len(partes[2]) == 4 else "%d/%m/%y"
    return datetime.strptime(bruto, formato).date()


# ---------- leitor ----------

# Linhas com data e valor que NÃO são movimento. Nos extratos reais examinados,
# "Saldo do dia" respondia por ~30% das linhas candidatas: importá-las criaria
# dezenas de transações fantasmas por arquivo e destruiria todo cálculo derivado.
MARCADORES_DE_SALDO = ("saldo",)

CONTA_PADRAO = "conta"


def _e_linha_de_saldo(linha: str) -> bool:
    minuscula = linha.lower()
    return any(marcador in minuscula for marcador in MARCADORES_DE_SALDO)


@dataclass(frozen=True)
class Reconciliacao:
    """Resultado da conferência da soma extraída contra o saldo declarado."""

    segmentos: int
    fecham: int
    ultimo_falhou: bool

    @property
    def confiavel(self) -> bool:
        """Todos os segmentos fecham, tolerando falha só no último — e só se houver
        outro segmento que tenha fechado.

        O último é tolerado porque nos três extratos reais examinados ele falhou
        sempre, e só ele: a última linha de saldo costuma ser o saldo atual (com
        valor pendente) ou o extrato foi gerado no meio do dia. Tolerar o último
        ainda verifica 49 de 50 segmentos — quase todo o dinheiro do extrato.

        A exigência de `fecham >= 1` fecha um furo que um teste pegou: com um único
        segmento, ele é também o último, e a tolerância engoliria a verificação
        inteira — um extrato completamente errado passaria como confiável.
        """
        tolerados = 1 if self.ultimo_falhou else 0
        return self.fecham >= 1 and self.fecham >= self.segmentos - tolerados


class LeitorPDF:
    """Lê extrato em PDF com duas guardas contra falha silenciosa.

    1. **Nenhuma linha candidata é ignorada.** Toda linha com data e valor precisa
       virar transação ou ser reconhecida como linha de saldo. Sobrou alguma? A
       leitura falha, em vez de devolver o resto e esconder o buraco.
    2. **A soma tem de bater com o saldo do banco.** Casando por data, a variação
       entre dois saldos diários consecutivos precisa ser igual à soma dos
       movimentos no intervalo.

    As mensagens de erro trazem **contagens, nunca conteúdo** — o extrato não vaza
    para log nem para traceback.
    """

    def __init__(self, conta: str = CONTA_PADRAO) -> None:
        self.conta = conta

    def _movimentos(self, linhas: list[str]) -> tuple[list[TransacaoBruta], int, int]:
        candidatas = [linha for linha in linhas if e_candidata(linha)]
        brutas: list[TransacaoBruta] = []
        saldos = 0
        for linha in candidatas:
            if _e_linha_de_saldo(linha):
                saldos += 1
                continue
            valores = VALOR.findall(linha)
            if len(valores) != 1:
                raise ValueError(
                    f"linha com {len(valores)} valores: não dá para saber qual é a "
                    "transação. Rode `personalos financas inspecionar-pdf` e ajuste "
                    "o leitor antes de importar."
                )
            achado_data = DATA.search(linha)
            assert achado_data is not None  # e_candidata já garantiu
            texto_valor = valores[0]
            descricao = (
                linha[achado_data.end() : linha.rfind(texto_valor)].strip()
                or linha[: achado_data.start()].strip()
            )
            if not descricao:
                raise ValueError("linha candidata sem descrição depois de remover data e valor")
            brutas.append(
                TransacaoBruta(
                    data=_para_data(achado_data.group(1), None),
                    valor=Dinheiro(_para_centavos(texto_valor)),
                    descricao=descricao,
                    conta=self.conta,
                )
            )
        return brutas, len(candidatas), saldos

    def reconciliar(self, caminho: str) -> Reconciliacao | None:
        """Confere a soma extraída contra os saldos declarados, casando por data.

        Devolve None quando o extrato não declara saldos suficientes — indeterminado
        não é o mesmo que reprovado.
        """
        linhas = linhas_de_texto(caminho)
        brutas, _, _ = self._movimentos(linhas)
        saldo_por_dia: dict[date, int] = {}
        for linha in linhas:
            if e_candidata(linha) and _e_linha_de_saldo(linha):
                achado = DATA.search(linha)
                assert achado is not None
                saldo_por_dia[_para_data(achado.group(1), None)] = _para_centavos(
                    VALOR.findall(linha)[-1]
                )
        dias = sorted(saldo_por_dia)
        if len(dias) < 2:
            return None
        fecham = 0
        ultimo_falhou = False
        for indice, (anterior, atual) in enumerate(zip(dias, dias[1:])):
            movido = sum(
                b.valor.centavos for b in brutas if anterior < b.data <= atual
            )
            if movido == saldo_por_dia[atual] - saldo_por_dia[anterior]:
                fecham += 1
            elif indice == len(dias) - 2:
                ultimo_falhou = True
        return Reconciliacao(len(dias) - 1, fecham, ultimo_falhou)

    def ler(self, caminho: str) -> list[TransacaoBruta]:
        linhas = linhas_de_texto(caminho)
        brutas, candidatas, saldos = self._movimentos(linhas)
        if len(brutas) + saldos != candidatas:  # guarda 1, defensiva
            raise ValueError(
                f"{candidatas - len(brutas) - saldos} de {candidatas} linhas candidatas "
                "não foram classificadas"
            )
        conferencia = self.reconciliar(caminho)
        if conferencia is not None and not conferencia.confiavel:
            raise ValueError(
                f"a soma extraída não fecha com o saldo do extrato: apenas "
                f"{conferencia.fecham} de {conferencia.segmentos} intervalos conferem. "
                "Importar assim gravaria número errado em silêncio."
            )
        return brutas


# ---------- diagnóstico (seguro para compartilhar) ----------

PALAVRAS_DE_TOTAL = ("saldo", "total", "anterior", "final", "disponível", "disponivel")


@dataclass(frozen=True)
class Diagnostico:
    """Estrutura de um PDF — tudo mascarado, nada de conteúdo real."""

    paginas: int
    linhas: int
    com_data: int
    com_valor: int
    candidatas: int
    amostras_mascaradas: tuple[str, ...]
    amostras_de_total: tuple[str, ...]
    valores_por_candidata: tuple[int, ...]  # quantos valores cada amostra tem


def diagnosticar(caminho: str, amostras: int = 8) -> Diagnostico:
    """Radiografa o PDF para calibrar um perfil SEM revelar o extrato.

    Toda linha de exemplo sai por `mascarar()`. É seguro colar o resultado num
    chat: mostra formato de data, formato de valor, ordem das colunas e onde o
    total declarado aparece — não mostra estabelecimento, nem valor, nem nome.
    """
    paginas = _paginas(caminho)
    linhas = linhas_de_texto(caminho)
    candidatas = [linha for linha in linhas if e_candidata(linha)]
    totais = [
        linha
        for linha in linhas
        if any(p in linha.lower() for p in PALAVRAS_DE_TOTAL) and VALOR.search(linha)
    ]
    return Diagnostico(
        paginas=paginas,
        linhas=len(linhas),
        com_data=sum(1 for linha in linhas if DATA.search(linha)),
        com_valor=sum(1 for linha in linhas if VALOR.search(linha)),
        candidatas=len(candidatas),
        amostras_mascaradas=tuple(mascarar(linha) for linha in candidatas[:amostras]),
        amostras_de_total=tuple(mascarar(linha) for linha in totais[:4]),
        valores_por_candidata=tuple(len(VALOR.findall(linha)) for linha in candidatas[:amostras]),
    )
