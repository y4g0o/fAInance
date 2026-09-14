"""Análises que respondem às perguntas de decisão — 100% determinístico.

Estas funções são as ferramentas que o agente conversacional chama. Ele escolhe
qual chamar e narra o resultado; **nenhum número aqui vem de LLM**.

Matemática de dinheiro parcelado usa `numpy_financial` (pacote oficial do NumPy):
`rate` resolve iterativamente o juro embutido em "10x de R$ 500" e `pmt` calcula a
parcela a partir de uma taxa — contas que erram fácil quando feitas à mão.
Estatística fica na stdlib de propósito: mediana e MAD não justificam dependência.
"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import median

import numpy_financial as npf
from sqlalchemy import text
from sqlalchemy.engine import Engine

from personalos.modulos.financas.dominio.modelos import e_consumo
from personalos.modulos.financas.insights import (
    gastos_fixos_conhecidos,
    normalizar_descricao,
)

MESES_MINIMOS_MEDIANA = 2  # com menos que isso a mediana não significa nada


# ---------- blocos comuns ----------


@dataclass(frozen=True)
class MesDespesas:
    mes: str
    fixo_centavos: int
    variavel_centavos: int
    receita_centavos: int


def _por_mes(engine: Engine, hoje: date | None = None) -> list[MesDespesas]:
    """Agrega por mês, separando o que é gasto fixo do que é variável.

    Exclui o mês corrente: um mês pela metade puxaria toda mediana para baixo.
    """
    chaves_fixas = {f.chave for f in gastos_fixos_conhecidos(engine)}
    with engine.connect() as conn:
        linhas = list(
            conn.execute(
                text(
                    "SELECT strftime('%Y-%m', data) AS mes, descricao, valor_centavos, "
                    "categoria FROM financas_transacoes ORDER BY data, fit_id"
                )
            )
        )
    corrente = (hoje or date.today()).strftime("%Y-%m")
    fixo: dict[str, int] = defaultdict(int)
    variavel: dict[str, int] = defaultdict(int)
    receita: dict[str, int] = defaultdict(int)
    meses: set[str] = set()
    for linha in linhas:
        mes = str(linha.mes)
        meses.add(mes)
        if linha.valor_centavos > 0:
            receita[mes] += linha.valor_centavos
        elif not e_consumo(linha.categoria):
            continue  # transferência própria e aplicação não são custo de vida
        elif normalizar_descricao(linha.descricao) in chaves_fixas:
            fixo[mes] += -linha.valor_centavos
        else:
            variavel[mes] += -linha.valor_centavos
    # Sem fallback para o mês corrente: um mês pela metade subestima a mediana, e um
    # custo básico subestimado é pior que nenhum — ele faz uma compra parecer caber.
    # Quem consome trata a lista vazia como "sem base", não como zero.
    completos = sorted(meses - {corrente})
    return [MesDespesas(m, fixo[m], variavel[m], receita[m]) for m in completos]


def _mediana(valores: list[int]) -> int:
    return int(median(valores)) if valores else 0


# ---------- custo básico ----------


@dataclass(frozen=True)
class CustoBasico:
    fixos_centavos: int          # soma das medianas dos gastos fixos ativos
    variavel_centavos: int       # mediana mensal do que sobra (variável)
    total_centavos: int
    fixos: tuple[tuple[str, int], ...]  # (descrição, valor mediano)
    meses_considerados: int


def custo_basico_mensal(engine: Engine, hoje: date | None = None) -> CustoBasico:
    """Quanto custa existir por mês: gastos fixos + a mediana do variável.

    Usa mediana (não média) porque um mês atípico não deve virar o seu normal.
    """
    fixos = sorted(gastos_fixos_conhecidos(engine), key=lambda f: -f.valor_mediano_centavos)
    soma_fixos = sum(f.valor_mediano_centavos for f in fixos)
    meses = _por_mes(engine, hoje)
    variavel = _mediana([m.variavel_centavos for m in meses])
    return CustoBasico(
        fixos_centavos=soma_fixos,
        variavel_centavos=variavel,
        total_centavos=soma_fixos + variavel,
        fixos=tuple((f.descricao_exemplo, f.valor_mediano_centavos) for f in fixos),
        meses_considerados=len(meses),
    )


# ---------- onde cortar ----------


@dataclass(frozen=True)
class Corte:
    descricao: str
    tipo: str  # "fixo" | "categoria"
    mensal_centavos: int
    anual_centavos: int


def onde_cortar(engine: Engine, limite: int = 5, hoje: date | None = None) -> list[Corte]:
    """Candidatos a corte ranqueados pelo impacto ANUAL — é o número que convence.

    Não julga o que é essencial: devolve os fatos ordenados. A conversa sobre "isso
    eu não posso cortar" é sua, não do algoritmo.
    """
    candidatos = [
        Corte(f.descricao_exemplo, "fixo", f.valor_mediano_centavos, f.valor_mediano_centavos * 12)
        for f in gastos_fixos_conhecidos(engine)
    ]
    chaves_fixas = {f.chave for f in gastos_fixos_conhecidos(engine)}

    with engine.connect() as conn:
        linhas = list(
            conn.execute(
                text(
                    "SELECT strftime('%Y-%m', data) AS mes, "
                    "COALESCE(categoria, 'Sem categoria') AS categoria, "
                    "descricao, valor_centavos FROM financas_transacoes "
                    "WHERE valor_centavos < 0 ORDER BY data, fit_id"
                )
            )
        )
    corrente = (hoje or date.today()).strftime("%Y-%m")
    por_categoria: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for linha in linhas:
        if (
            str(linha.mes) == corrente
            or not e_consumo(linha.categoria)
            or normalizar_descricao(linha.descricao) in chaves_fixas
        ):
            continue  # mês incompleto distorce; não-consumo não é corte; fixo já entrou
        por_categoria[str(linha.categoria)][str(linha.mes)] += -linha.valor_centavos

    for categoria, meses in por_categoria.items():
        if len(meses) < MESES_MINIMOS_MEDIANA:
            continue
        mensal = _mediana(list(meses.values()))
        if mensal > 0:
            candidatos.append(Corte(categoria, "categoria", mensal, mensal * 12))

    return sorted(candidatos, key=lambda c: (-c.anual_centavos, c.descricao))[:limite]


# ---------- vale a pena comprar? ----------


@dataclass(frozen=True)
class Compra:
    valor_centavos: int
    parcelas: int
    parcela_centavos: int
    custo_total_centavos: int
    juros_centavos: int
    taxa_mensal: float | None      # implícita quando a loja dá o valor da parcela
    folga_mensal_centavos: int     # receita mediana − custo básico
    percentual_da_folga: float | None
    meses_de_reserva: float | None  # saldo atual ÷ custo básico
    custo_basico_centavos: int


def pode_comprar(
    engine: Engine,
    valor_centavos: int,
    parcelas: int = 1,
    taxa_mensal: float = 0.0,
    parcela_centavos: int | None = None,
    hoje: date | None = None,
) -> Compra:
    """Os números de uma compra, sem veredito.

    Dois modos:
    - a loja diz "10x de R$ 500": passe `parcela_centavos` e a taxa mensal embutida
      é recuperada por `npf.rate` (é aqui que o "sem juros" costuma não ser);
    - você sabe a taxa: passe `taxa_mensal` e a parcela sai de `npf.pmt`.
    """
    if valor_centavos <= 0:
        raise ValueError("valor deve ser positivo")
    if parcelas < 1:
        raise ValueError("parcelas deve ser >= 1")

    taxa: float | None
    if parcela_centavos is not None:
        parcela = parcela_centavos
        taxa = None
        if parcelas > 1:
            bruta = float(npf.rate(parcelas, -parcela_centavos, valor_centavos, 0))
            taxa = bruta if bruta == bruta and abs(bruta) < 10 else None  # NaN-safe
    elif taxa_mensal > 0 and parcelas > 1:
        parcela = int(round(-float(npf.pmt(taxa_mensal, parcelas, valor_centavos))))
        taxa = taxa_mensal
    else:
        parcela = int(round(valor_centavos / parcelas))
        taxa = 0.0

    total = parcela * parcelas
    basico = custo_basico_mensal(engine, hoje)
    meses = _por_mes(engine, hoje)
    receita = _mediana([m.receita_centavos for m in meses])
    folga = receita - basico.total_centavos

    with engine.connect() as conn:
        saldo = int(
            conn.execute(text("SELECT saldo_centavos FROM vw_financas_saldo_v1")).scalar() or 0
        )

    return Compra(
        valor_centavos=valor_centavos,
        parcelas=parcelas,
        parcela_centavos=parcela,
        custo_total_centavos=total,
        juros_centavos=total - valor_centavos,
        taxa_mensal=taxa,
        folga_mensal_centavos=folga,
        percentual_da_folga=(parcela / folga) if folga > 0 else None,
        meses_de_reserva=(saldo / basico.total_centavos) if basico.total_centavos > 0 else None,
        custo_basico_centavos=basico.total_centavos,
    )


# ---------- como o mês vai fechar ----------


@dataclass(frozen=True)
class Projecao:
    mes: str
    dias_corridos: int
    dias_no_mes: int
    gasto_ate_agora_centavos: int
    fixos_pendentes_centavos: int
    projecao_centavos: int
    receita_prevista_centavos: int


def projecao_fim_do_mes(engine: Engine, hoje: date | None = None) -> Projecao | None:
    """Ritmo de gasto do mês projetado até o fim, mais os fixos que ainda não caíram.

    Devolve None se o mês corrente não tem movimento nenhum — projetar do nada seria
    inventar número.
    """
    referencia = hoje or date.today()
    mes = referencia.strftime("%Y-%m")
    chaves_fixas = {f.chave: f for f in gastos_fixos_conhecidos(engine)}

    with engine.connect() as conn:
        linhas = list(
            conn.execute(
                text(
                    "SELECT descricao, valor_centavos, categoria FROM financas_transacoes "
                    "WHERE strftime('%Y-%m', data) = :mes"
                ),
                {"mes": mes},
            )
        )
    if not linhas:
        return None

    gasto = sum(
        -linha.valor_centavos
        for linha in linhas
        if linha.valor_centavos < 0 and e_consumo(linha.categoria)
    )
    vistos = {normalizar_descricao(linha.descricao) for linha in linhas}
    pendentes = sum(
        fixo.valor_mediano_centavos for chave, fixo in chaves_fixas.items() if chave not in vistos
    )
    gasto_fixo_ja_pago = sum(
        -linha.valor_centavos
        for linha in linhas
        if linha.valor_centavos < 0 and normalizar_descricao(linha.descricao) in chaves_fixas
    )

    dias_no_mes = monthrange(referencia.year, referencia.month)[1]
    dias_corridos = min(referencia.day, dias_no_mes)
    # Projeta pelo ritmo só a parte VARIÁVEL; fixo não se acelera com os dias.
    variavel = max(gasto - gasto_fixo_ja_pago, 0)
    ritmo = int(variavel / dias_corridos * dias_no_mes) if dias_corridos else variavel

    meses = _por_mes(engine, referencia)
    return Projecao(
        mes=mes,
        dias_corridos=dias_corridos,
        dias_no_mes=dias_no_mes,
        gasto_ate_agora_centavos=gasto,
        fixos_pendentes_centavos=pendentes,
        projecao_centavos=gasto_fixo_ja_pago + ritmo + pendentes,
        receita_prevista_centavos=_mediana([m.receita_centavos for m in meses]),
    )
