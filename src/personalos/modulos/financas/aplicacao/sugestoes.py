"""Sugestão de regras de categorização — determinístico, sem LLM.

Problema que resolve: depois de importar um ano de extrato, todas as transações
nascem sem categoria, e criar regra de uma em uma para centenas de linhas é
inviável. Aqui as transações sem categoria são agrupadas pela mesma normalização
que a detecção de gasto fixo usa, e cada grupo vira uma sugestão com o volume que
ela cobre — assim meia dúzia de regras resolve a maior parte do dinheiro.

O que NÃO faz: escolher a categoria. Nomear é julgamento do usuário; a ferramenta
só mostra onde está o volume.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

from personalos.modulos.financas.dominio.categorizador import categorizar
from personalos.modulos.financas.infra.repositorios import RepoRegrasSQL, RepoTransacoesSQL
from personalos.modulos.financas.insights import limpar_descricao, normalizar_descricao
from personalos.nucleo.transacao import escrita

# Palavra com 3+ letras. Números e pontuação ficam fora porque o padrão precisa ser
# estável entre ocorrências, e é neles que o banco escreve data, parcela e documento.
_PALAVRA = re.compile(r"[a-zA-ZÀ-ú]{3,}")


@dataclass(frozen=True)
class SugestaoRegra:
    padrao: str            # substring a usar em `financas regra`
    exemplo: str           # como aparece no extrato, para o humano reconhecer
    ocorrencias: int       # transações sem categoria neste grupo
    total_centavos: int    # quanto de dinheiro o grupo representa (magnitude)
    alcance: int           # transações que o padrão pegaria, inclusive já categorizadas


def _padrao_comum(descricoes: list[str]) -> str | None:
    """Palavra mais longa presente em TODAS as descrições do grupo.

    O comprimento é um proxy simples de distintividade: entre "PIX", "QRS" e
    "TELECOMIX", a última é a que identifica o gasto. Não precisa de lista de palavras
    genéricas — e listas dessas envelhecem mal.

    Empate é resolvido por ordem alfabética, não pela ordem do `set`: um teste pegou
    que `max()` sobre conjunto é **não determinístico** em empate, o que faria a
    sugestão mudar entre execuções sobre os mesmos dados.
    """
    conjuntos = [
        {p.lower() for p in _PALAVRA.findall(descricao)} for descricao in descricoes
    ]
    if not conjuntos:
        return None
    comuns = set.intersection(*conjuntos)
    return max(comuns, key=lambda palavra: (len(palavra), palavra)) if comuns else None


def sugerir_regras(
    engine: Engine, limite: int = 10, minimo_de_ocorrencias: int = 2
) -> list[SugestaoRegra]:
    """Grupos de transações sem categoria, ordenados pelo dinheiro que representam.

    Ordena por total e não por contagem: uma regra que cobre três gastos grandes vale
    mais que uma que cobre trinta cafés.
    """
    with engine.connect() as conn:
        linhas = list(
            conn.execute(
                text(
                    "SELECT descricao, valor_centavos, categoria "
                    "FROM financas_transacoes WHERE valor_centavos < 0 "
                    "ORDER BY data, fit_id"
                )
            )
        )
    grupos: dict[str, list[tuple[str, int]]] = defaultdict(list)
    todas: list[str] = []
    for linha in linhas:
        todas.append(str(linha.descricao))
        if linha.categoria is None:
            chave = normalizar_descricao(str(linha.descricao))
            if chave:
                grupos[chave].append((str(linha.descricao), -int(linha.valor_centavos)))

    sugestoes: list[SugestaoRegra] = []
    for _chave, itens in grupos.items():
        if len(itens) < minimo_de_ocorrencias:
            continue
        padrao = _padrao_comum([descricao for descricao, _ in itens])
        if padrao is None:
            continue
        sugestoes.append(
            SugestaoRegra(
                padrao=padrao,
                exemplo=limpar_descricao(itens[-1][0]),
                ocorrencias=len(itens),
                total_centavos=sum(valor for _, valor in itens),
                alcance=sum(1 for descricao in todas if padrao in descricao.lower()),
            )
        )
    return sorted(sugestoes, key=lambda s: (-s.total_centavos, s.padrao))[:limite]


def recategorizar(engine: Engine, reaplicar_tudo: bool = False) -> int:
    """Aplica as regras atuais às transações JÁ gravadas. Devolve quantas mudaram.

    Existe porque criar regra depois de importar não fazia nada: o `INSERT OR IGNORE`
    do importador pula linhas existentes, então reimportar não recategoriza — e a
    própria saída de `sugerir-regras` instruía o usuário a reimportar, ou seja
    mandava fazer algo que não funcionava.

    Por padrão só preenche o que está SEM categoria: sobrescrever categoria já
    atribuída destruiria correção manual. `reaplicar_tudo=True` é a saída explícita
    para quando uma regra mudou e você quer propagar.
    """
    repo_tx = RepoTransacoesSQL(engine)
    regras = RepoRegrasSQL(engine).listar()
    if not regras:
        return 0
    mudadas = 0
    with escrita(engine) as conn:
        for transacao in repo_tx.listar():
            if transacao.categoria is not None and not reaplicar_tudo:
                continue
            nova = categorizar(transacao, regras)
            if nova is None or nova == transacao.categoria:
                continue
            conn.execute(
                text(
                    "UPDATE financas_transacoes SET categoria = :cat WHERE fit_id = :fit"
                ),
                {"cat": nova, "fit": transacao.fit_id},
            )
            mudadas += 1
    return mudadas
