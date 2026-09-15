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
import unicodedata
from collections import Counter, defaultdict
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


# Palavra presente em mais que esta fração das descrições não identifica nada
# NESTE extrato — e cada banco tem o seu vocabulário de enchimento.
FRACAO_BANAL = 0.25
MINIMO_PARA_MEDIR_BANALIDADE = 20


def palavras_banais(descricoes: list[str], fracao: float = FRACAO_BANAL) -> frozenset[str]:
    """Palavras comuns demais para servirem de padrão, medidas no próprio dado.

    Lista fixa não resolve: ela acerta o banco que se conhecia quando foi escrita
    e erra o próximo. O Nubank escreve "Transferência enviada pelo Pix - NOME" em
    centenas de linhas, e sem isto o padrão sugerido para todos os grupos virava
    "transferência" — uma regra que pegaria tudo.
    """
    # Em conjunto pequeno, palavra repetida É o padrão — não há como distinguir
    # enchimento de identidade com cinco linhas. O filtro só liga quando há dado
    # suficiente para a frequência significar alguma coisa.
    if len(descricoes) < MINIMO_PARA_MEDIR_BANALIDADE:
        return frozenset()
    contagem: Counter[str] = Counter()
    for descricao in descricoes:
        contagem.update({_sem_acento(p) for p in _PALAVRA.findall(descricao)})
    corte = max(5, int(len(descricoes) * fracao))
    return frozenset(palavra for palavra, n in contagem.items() if n >= corte)


def _padrao_comum(descricoes: list[str], banais: frozenset[str] = frozenset()) -> str | None:
    """Palavra mais longa presente em TODAS as descrições do grupo.

    O comprimento é um proxy simples de distintividade: entre "PIX", "QRS" e
    "TELECOMIX", a última é a que identifica o gasto. Não precisa de lista de palavras
    genéricas — e listas dessas envelhecem mal.

    Empate é resolvido por ordem alfabética, não pela ordem do `set`: um teste pegou
    que `max()` sobre conjunto é **não determinístico** em empate, o que faria a
    sugestão mudar entre execuções sobre os mesmos dados.
    """
    conjuntos = [
        {p.lower() for p in _PALAVRA.findall(descricao) if _sem_acento(p) not in banais}
        for descricao in descricoes
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
    banais = palavras_banais([str(linha.descricao) for linha in linhas])
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
        padrao = _padrao_comum([descricao for descricao, _ in itens], banais)
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


@dataclass(frozen=True)
class SugestaoCategoria:
    categoria: str
    palavra: str      # a palavra que casou — é a justificativa da sugestão
    transacoes: int   # em quantas transações já categorizadas ela aparece


# Uma transação é coincidência; duas começam a ser padrão. Mesmo limiar do agrupador.
MINIMO_PARA_SUGERIR = 2

# Palavras que aparecem em quase toda descrição de extrato e não identificam nada.
_GENERICAS = frozenset({
    "compra", "debito", "credito", "pagamento", "pix", "qrs", "transf",
    "transferencia", "conta", "cartao", "fatura", "para", "pelo", "pela",
})


def _sem_acento(palavra: str) -> str:
    """Compara palavra ignorando acento.

    Falha real: a lista de genéricas tinha 'debito' e o extrato escreve 'débito',
    então a palavra que aparece em TODA descrição passou a ser a mais distintiva
    — e o sistema sugeriu Delivery para supermercado.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", palavra.lower())
        if unicodedata.category(c) != "Mn"
    )


def sugerir_categoria(engine: Engine, descricao: str) -> SugestaoCategoria | None:
    """Sugere categoria a partir do que o usuário JÁ categorizou.

    Não é palpite: a sugestão só existe se alguma palavra distintiva da descrição
    aparecer em transações que ele mesmo classificou. Devolve a palavra e a
    contagem porque sugestão sem justificativa é adivinhação com cara de
    autoridade — e aqui quem decide continua sendo ele.

    Sem precedente, devolve None. Campo vazio é melhor que sugestão inventada.

    Duas exigências que vieram de sugestões ruins observadas nos dados reais:
    ao menos DUAS transações sustentando (uma é coincidência, não padrão), e
    nunca sugerir categoria declarada como movimentação — sugerir "Conta de uso"
    para uma compra é sugerir que ela não é gasto, e o usuário aceitaria sem ver.
    """
    from personalos.modulos.financas.aplicacao.escrita import categorias_nao_consumo
    from personalos.modulos.financas.dominio.modelos import e_consumo

    nao_consumo = categorias_nao_consumo(engine)
    palavras = {
        p.lower() for p in _PALAVRA.findall(descricao)
        if len(p) >= 4 and _sem_acento(p) not in _GENERICAS
    }
    if not palavras:
        return None

    with engine.connect() as conn:
        linhas = conn.execute(
            text(
                "SELECT descricao, categoria FROM financas_transacoes "
                "WHERE categoria IS NOT NULL AND categoria <> ''"
            )
        ).all()

    placar: dict[tuple[str, str], int] = defaultdict(int)
    for linha in linhas:
        if not e_consumo(str(linha.categoria), nao_consumo):
            continue
        presentes = {_sem_acento(p) for p in _PALAVRA.findall(str(linha.descricao))}
        for palavra in {p for p in palavras if _sem_acento(p) in presentes}:
            placar[(str(linha.categoria), palavra)] += 1

    if not placar:
        return None
    # Mais transações ganha; empate resolve pela palavra mais longa (mais
    # distintiva) e depois alfabeticamente, para a sugestão não mudar entre execuções.
    (categoria, palavra), quantas = max(
        placar.items(), key=lambda kv: (kv[1], len(kv[0][1]), kv[0][1])
    )
    if quantas < MINIMO_PARA_SUGERIR:
        return None
    return SugestaoCategoria(categoria=categoria, palavra=palavra, transacoes=quantas)
