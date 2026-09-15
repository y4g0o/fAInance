"""Gastos fixos aprendidos e regras de alerta — 100% determinístico, sem LLM.

Todo número aqui vem de SQL/Python sobre as transações. O LLM (no bot) só serve
para conversar sobre o resultado; ele nunca detecta nem calcula um gasto fixo.

Como um gasto fixo é reconhecido: agrupa as despesas por descrição normalizada
(sem dígitos nem pontuação, que é onde os bancos escrevem data e nº de parcela) e
aceita o grupo quando aparece em pelo menos MESES_MINIMOS meses distintos, com
valor estável (a maioria das ocorrências perto da mediana) e atividade recente.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import Engine

from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import e_consumo
from personalos.nucleo import memoria
from personalos.nucleo.modulo import Insight, RegraInsight

MODULO = "financas"
TIPO_FATO = "gasto_fixo"
# Decisão do usuário de que algo NÃO é gasto fixo. Precisa ser guardada: apagar
# só o fato aprendido dura até o próximo `importar`, que reaprende na hora — a
# correção evaporava sem ninguém perceber.
TIPO_IGNORADO = "gasto_fixo_ignorado"

MESES_MINIMOS = 3          # menos que isso é coincidência, não hábito
TOLERANCIA_VALOR = 0.25    # ±25% da mediana ainda é "o mesmo" gasto fixo
FRACAO_ESTAVEL = 2 / 3     # fração das ocorrências que precisa estar na tolerância
MESES_INATIVIDADE = 2      # sem aparecer por mais que isso, deixou de ser fixo
AUMENTO_RELEVANTE = 0.10   # 10% acima da mediana já merece aviso
FATOR_CATEGORIA = 1.30     # limiar relativo de reserva, quando o MAD não serve


@dataclass(frozen=True)
class GastoFixo:
    chave: str                 # descrição normalizada — identidade do fixo
    descricao_exemplo: str     # como aparece no extrato, para o humano reconhecer
    valor_mediano_centavos: int
    ocorrencias: int
    meses: tuple[str, ...]     # YYYY-MM em que apareceu
    ultima_data: str
    ultimo_valor_centavos: int
    dia_tipico: int            # mediana do dia do mês — define quando o gasto é esperado


def normalizar_descricao(descricao: str) -> str:
    """Remove dígitos e pontuação (data, parcela, nº do documento) e normaliza espaços.

    Pública porque é a chave de identidade de um gasto fixo: quem precisa saber se
    uma transação pertence a um fixo conhecido tem de normalizar do mesmo jeito.
    """
    sem_digitos = re.sub(r"\d+", " ", descricao.lower())
    apenas_palavras = re.sub(r"[^a-zà-ú\s]+", " ", sem_digitos)
    return re.sub(r"\s+", " ", apenas_palavras).strip()


# Data colada no fim da descrição, como os extratos truncam: "PIX QRS TELECOMIX05/08".
_DATA_NO_FIM = re.compile(r"\s*\d{2}/\d{2}(?:/\d{2,4})?\s*$")


def limpar_descricao(descricao: str) -> str:
    """Remove a data colada no fim, para EXIBIÇÃO.

    Diferente de `normalizar_descricao`, que remove todo dígito para formar a chave
    de identidade: aqui o objetivo é legibilidade, então números que fazem parte do
    nome (um número de documento, por exemplo) são preservados.
    """
    return _DATA_NO_FIM.sub("", descricao).strip()


def _meses_entre(inicio: str, fim: str) -> int:
    (ai, mi), (af, mf) = (int(x) for x in inicio.split("-")), (int(x) for x in fim.split("-"))
    return (af - ai) * 12 + (mf - mi)


def _despesas(engine: Engine) -> list[tuple[str, str, int]]:
    """(data, descricao, valor_centavos) das despesas de CONSUMO, em ordem determinística.

    Transferência entre contas próprias e aplicação são filtradas: uma transferência
    mensal de valor estável tem toda a cara de gasto fixo, e seria o maior deles —
    precisa ser excluída pela natureza, não pelo valor.
    """
    with engine.connect() as conn:
        return [
            (r.data, r.descricao, r.valor_centavos)
            for r in conn.execute(
                text(
                    "SELECT data, descricao, valor_centavos, categoria "
                    "FROM vw_financas_despesas_v1"
                )
            )
            if e_consumo(r.categoria)
        ]


def detectar_gastos_fixos(engine: Engine, hoje: date | None = None) -> list[GastoFixo]:
    """Detecta os gastos fixos a partir do histórico. Pura: não grava nada."""
    despesas = _despesas(engine)
    if not despesas:
        return []
    referencia = (hoje or date.today()).strftime("%Y-%m")

    grupos: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for data_iso, descricao, centavos in despesas:
        chave = normalizar_descricao(descricao)
        if chave:
            grupos[chave].append((data_iso, descricao, abs(centavos)))

    fixos: list[GastoFixo] = []
    for chave, ocorrencias in sorted(grupos.items()):
        meses = sorted({d[:7] for d, _, _ in ocorrencias})
        if len(meses) < MESES_MINIMOS:
            continue
        if _meses_entre(meses[-1], referencia) > MESES_INATIVIDADE:
            continue  # parou de acontecer: não é mais um fixo ativo
        valores = [c for _, _, c in ocorrencias]
        central = median(valores)
        estaveis = sum(1 for v in valores if abs(v - central) <= TOLERANCIA_VALOR * central)
        if estaveis < FRACAO_ESTAVEL * len(valores):
            continue  # recorrente mas de valor imprevisível (mercado, por exemplo)
        ultima = max(ocorrencias, key=lambda o: (o[0], o[2]))
        dia_tipico = int(median([int(d[8:10]) for d, _, _ in ocorrencias]))
        fixos.append(
            GastoFixo(
                chave=chave,
                descricao_exemplo=limpar_descricao(ultima[1]),
                valor_mediano_centavos=int(central),
                ocorrencias=len(ocorrencias),
                meses=tuple(meses),
                ultima_data=ultima[0],
                ultimo_valor_centavos=ultima[2],
                dia_tipico=dia_tipico,
            )
        )
    return fixos


def aprender_gastos_fixos(engine: Engine, hoje: date | None = None) -> list[GastoFixo]:
    """Detecta e guarda em nucleo_memoria. Reaprender atualiza, não duplica.

    Não remove fatos que deixaram de ser detectados: se você corrigiu ou nomeou um
    fixo, apagá-lo é decisão sua (`personalos financas esquecer-fixo`).

    O que o usuário mandou esquecer fica de fora **para sempre**: a decisão dele
    vale mais que o critério estatístico, e sem isso ela duraria até o próximo
    extrato.
    """
    ignorados = {f.chave for f in memoria.listar(engine, MODULO, TIPO_IGNORADO)}
    fixos = [f for f in detectar_gastos_fixos(engine, hoje) if f.chave not in ignorados]
    for fixo in fixos:
        memoria.definir(
            engine, MODULO, TIPO_FATO, fixo.chave,
            {
                "descricao_exemplo": fixo.descricao_exemplo,
                "valor_mediano_centavos": fixo.valor_mediano_centavos,
                "ocorrencias": fixo.ocorrencias,
                "meses": list(fixo.meses),
                "ultima_data": fixo.ultima_data,
                "ultimo_valor_centavos": fixo.ultimo_valor_centavos,
                "dia_tipico": fixo.dia_tipico,
            },
        )
    return fixos


def gastos_fixos_conhecidos(engine: Engine) -> list[GastoFixo]:
    """Gastos fixos já aprendidos, lidos de nucleo_memoria e tipados.

    Único ponto que interpreta o JSON da memória — regras e análises trabalham
    sobre GastoFixo, nunca sobre dict.
    """
    return [
        GastoFixo(
            chave=f.chave,
            descricao_exemplo=str(f.valor["descricao_exemplo"]),
            valor_mediano_centavos=cast(int, f.valor["valor_mediano_centavos"]),
            ocorrencias=cast(int, f.valor["ocorrencias"]),
            meses=tuple(str(m) for m in cast(list, f.valor["meses"])),
            ultima_data=str(f.valor["ultima_data"]),
            ultimo_valor_centavos=cast(int, f.valor["ultimo_valor_centavos"]),
            # default 1 para fatos gravados antes deste campo existir
            dia_tipico=cast(int, f.valor.get("dia_tipico", 1)),
        )
        for f in memoria.listar(engine, MODULO, TIPO_FATO)
    ]


def _fora_do_normal(atual: int, anteriores: list[int]) -> bool:
    """Outlier por z-score modificado (Iglewicz-Hoaglin): mediana + MAD, corte 3,5.

    Mediana e MAD em vez de média e desvio padrão porque um único mês absurdo
    contamina a média e o desvio — justamente o mês que queremos detectar.

    Com poucos meses o MAD costuma dar zero (valores quase idênticos), e aí
    qualquer diferença viraria "infinitamente anormal". Nesse caso cai no
    critério relativo simples de FATOR_CATEGORIA, que é honesto sobre ser um
    limiar arbitrário em vez de fingir rigor estatístico.
    """
    centro = median(anteriores)
    mad = median([abs(v - centro) for v in anteriores])
    if mad == 0 or len(anteriores) < 4:
        return centro > 0 and atual > centro * FATOR_CATEGORIA
    return 0.6745 * (atual - centro) / mad > 3.5


def _ultima_data_com_dados(engine: Engine) -> str | None:
    with engine.connect() as conn:
        return conn.execute(text("SELECT MAX(data) FROM financas_transacoes")).scalar()


# ---------- regras ----------


def regra_fixo_ausente(engine: Engine) -> list[Insight]:
    """Gasto fixo conhecido que não apareceu no último mês com movimento.

    Dois cortes, cada um contra uma fonte de ruído medida em dados reais:

    1. **Ausência recente** (até MESES_INATIVIDADE meses após a última ocorrência).
       Sem isso, uma assinatura cancelada de propósito geraria alerta novo todo mês
       para sempre — e como a chave de dedup inclui o mês, dispensar um não calaria o
       do mês seguinte.
    2. **Dia habitual já vencido.** O último mês com dados costuma estar incompleto:
       se o extrato termina no dia 5, quase todo gasto mensal "não apareceu" ainda.
       Encontrado nos extratos reais do usuário — 4 de 6 fixos foram acusados
       indevidamente. Alertar antes do vencimento treina o usuário a ignorar a lista.
    """
    ultima_data = _ultima_data_com_dados(engine)
    if ultima_data is None:
        return []
    mes, dia_disponivel = ultima_data[:7], int(ultima_data[8:10])
    insights: list[Insight] = []
    for fixo in gastos_fixos_conhecidos(engine):
        if mes in fixo.meses:
            continue
        if not fixo.meses or _meses_entre(fixo.meses[-1], mes) > MESES_INATIVIDADE:
            continue  # deixou de ser fixo ativo: virou história, não alerta
        if fixo.dia_tipico > dia_disponivel:
            continue  # ainda não venceu no período coberto pelo extrato
        insights.append(
            Insight(
                chave_dedup=f"{fixo.chave}:{mes}",
                titulo=f"'{fixo.descricao_exemplo}' não apareceu em {mes}",
                detalhe={
                    "gasto_fixo": fixo.chave,
                    "mes": mes,
                    "valor_mediano_centavos": fixo.valor_mediano_centavos,
                    "meses_conhecidos": list(fixo.meses),
                },
                severidade="atencao",
            )
        )
    return insights


def regra_fixo_aumentou(engine: Engine) -> list[Insight]:
    """Gasto fixo cuja última ocorrência ficou acima da mediana histórica."""
    insights: list[Insight] = []
    for fixo in gastos_fixos_conhecidos(engine):
        mediana, ultimo = fixo.valor_mediano_centavos, fixo.ultimo_valor_centavos
        if mediana <= 0 or ultimo <= mediana * (1 + AUMENTO_RELEVANTE):
            continue
        alta = (ultimo - mediana) / mediana
        insights.append(
            Insight(
                chave_dedup=f"{fixo.chave}:{fixo.ultima_data}",
                titulo=(
                    f"'{fixo.descricao_exemplo}' subiu {alta:.0%} "
                    f"(de {Dinheiro(mediana).formatar()} para {Dinheiro(ultimo).formatar()})"
                ),
                detalhe={
                    "gasto_fixo": fixo.chave,
                    "valor_mediano_centavos": mediana,
                    "valor_atual_centavos": ultimo,
                    "data": fixo.ultima_data,
                },
                severidade="alerta" if alta >= 0.3 else "atencao",
            )
        )
    return insights


def regra_categoria_acima_da_media(engine: Engine) -> list[Insight]:
    """Categoria que estourou a própria média dos 6 meses anteriores."""
    ultima_data = _ultima_data_com_dados(engine)
    if ultima_data is None:
        return []
    mes = ultima_data[:7]
    with engine.connect() as conn:
        linhas = list(
            conn.execute(
                text(
                    """
                    SELECT COALESCE(categoria, 'Sem categoria') AS categoria,
                           strftime('%Y-%m', data) AS mes,
                           SUM(-valor_centavos) AS total
                    FROM financas_transacoes
                    WHERE valor_centavos < 0
                      AND strftime('%Y-%m', data) > strftime('%Y-%m', date(:mes || '-01', '-7 months'))
                    GROUP BY categoria, mes
                    ORDER BY categoria, mes
                    """
                ),
                {"mes": mes},
            )
        )
    por_categoria: dict[str, dict[str, int]] = defaultdict(dict)
    for linha in linhas:
        por_categoria[linha.categoria][linha.mes] = int(linha.total)

    insights: list[Insight] = []
    for categoria, meses in sorted(por_categoria.items()):
        atual = meses.get(mes)
        anteriores = [v for m, v in meses.items() if m < mes]
        if atual is None or len(anteriores) < 2:
            continue  # sem base de comparação, não há "fora do normal"
        if not _fora_do_normal(atual, anteriores):
            continue
        referencia = median(anteriores)
        insights.append(
            Insight(
                chave_dedup=f"{categoria}:{mes}",
                titulo=(
                    f"{categoria} em {mes}: {Dinheiro(atual).formatar()} "
                    f"({atual / referencia - 1:+.0%} vs. mediana de "
                    f"{Dinheiro(int(referencia)).formatar()})"
                ),
                detalhe={
                    "categoria": categoria,
                    "mes": mes,
                    "total_centavos": atual,
                    "mediana_anterior_centavos": int(referencia),
                    "meses_comparados": len(anteriores),
                },
                severidade="atencao",
            )
        )
    return insights


REGRAS: tuple[RegraInsight, ...] = (
    RegraInsight("financas_fixo_ausente", regra_fixo_ausente),
    RegraInsight("financas_fixo_aumentou", regra_fixo_aumentou),
    RegraInsight("financas_categoria_acima_da_media", regra_categoria_acima_da_media),
)


def esquecer_fixo(engine: Engine, chave: str) -> bool:
    """Esquece um gasto fixo E registra que ele não deve voltar a ser aprendido.

    Guardar a decisão é o ponto: compra recorrente de marketplace atende ao
    critério (3 meses, valor parecido) e será redetectada a cada importação.
    Sem o registro, o usuário esqueceria o mesmo gasto todo mês.
    """
    existia = memoria.remover(engine, MODULO, TIPO_FATO, chave)
    memoria.definir(engine, MODULO, TIPO_IGNORADO, chave, {"motivo": "decisão do usuário"})
    return existia
