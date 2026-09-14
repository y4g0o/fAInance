"""Caso de uso: importar extratos → dedup (fit_id estável) → categorizar → persistir."""
from __future__ import annotations

import hashlib
from collections import Counter

from personalos.modulos.financas.aplicacao.portas import (
    RepoRegras,
    RepoTransacoes,
    SeletorLeitor,
    TransacaoBruta,
)
from personalos.modulos.financas.dominio.categorizador import categorizar
from personalos.modulos.financas.dominio.modelos import Transacao


def fit_id_estavel(b: TransacaoBruta, ocorrencia: int) -> str:
    """Hash estável de (conta, data, centavos, descrição, ocorrência-no-arquivo).

    Idempotente ao reimportar o mesmo arquivo, e preserva duplicatas legítimas
    (duas compras iguais no mesmo dia recebem ocorrências 0 e 1).

    A `ocorrencia` é contada **por arquivo**: é o que faz extratos sobrepostos da
    mesma conta convergirem para o mesmo fit_id, em vez de duplicarem o gasto.
    Limite conhecido: duas contas distintas cujo leitor devolva o mesmo rótulo em
    `conta` colidiriam — hoje não acontece porque o rótulo vem do formato do
    arquivo, mas é o ponto a revisitar se um leitor novo passar a inferir conta."""
    base = f"{b.conta}|{b.data.isoformat()}|{b.valor.centavos}|{b.descricao}|{ocorrencia}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def _com_fit_id(
    brutas: list[TransacaoBruta], contador: "Counter[tuple[str, str, int, str]]"
) -> list[tuple[TransacaoBruta, str]]:
    out: list[tuple[TransacaoBruta, str]] = []
    for b in brutas:
        if b.fit_id:
            out.append((b, b.fit_id))
            continue
        chave = (b.conta, b.data.isoformat(), b.valor.centavos, b.descricao)
        ocorr = contador[chave]
        contador[chave] += 1
        out.append((b, fit_id_estavel(b, ocorr)))
    return out


def importar_extratos(
    caminhos: list[str],
    repo_tx: RepoTransacoes,
    repo_regras: RepoRegras,
    selecionar_leitor: SeletorLeitor,
) -> int:
    regras = repo_regras.listar()
    transacoes: list[Transacao] = []
    for caminho in sorted(caminhos):
        # Contador POR ARQUIVO, não por chamada. Extratos do mesmo banco se
        # sobrepõem (o "últimos 90 dias" baixado três vezes cobre os mesmos meses),
        # e um contador global daria à mesma transação a ocorrência 0 no primeiro
        # arquivo e 1 no segundo — dois fit_id, duas linhas, gasto em dobro.
        # Reiniciando por arquivo, a mesma transação recebe o mesmo fit_id nos dois
        # e o INSERT OR IGNORE a absorve, enquanto duas compras iguais de verdade
        # dentro de um extrato continuam sendo duas (ocorrências 0 e 1).
        contador: Counter[tuple[str, str, int, str]] = Counter()
        brutas = selecionar_leitor(caminho).ler(caminho)
        for b, fit in _com_fit_id(brutas, contador):
            t = Transacao(fit, b.data, b.valor, b.descricao, b.conta)
            categoria = categorizar(t, regras)
            transacoes.append(
                Transacao(fit, b.data, b.valor, b.descricao, b.conta, categoria)
            )
    return repo_tx.inserir_muitas(transacoes)
