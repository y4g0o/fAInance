"""Endpoints do módulo financas, montados em /api/financas.

Sem camada de DTO: as dataclasses de `aplicacao/` são o modelo de resposta direto.
FastAPI serializa dataclass stdlib, e um mapeamento a mais é um mapeamento que pode
desincronizar. Gatilho para criar DTO: o primeiro campo que precise de nome
diferente na web.

Nenhuma aritmética aqui — toda função vem de `aplicacao/`, a mesma que a CLI usa.
É o que garante que painel, API e terminal não possam divergir.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Engine

from personalos.api.dependencias import obter_engine
from personalos.modulos.financas.aplicacao import analise, consultas, escrita, sugestoes
from personalos.modulos.financas.aplicacao.importar import importar_extratos
from personalos.modulos.financas.infra.leitores import detectar_leitor
from personalos.nucleo.config import diretorio_extratos
from personalos.modulos.financas.aplicacao.resumo import resumo
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.infra.repositorios import (
    RepoContasSQL,
    RepoRegrasSQL,
    RepoTransacoesSQL,
)
from personalos.nucleo.modulo import CardResumo

Motor = Annotated[Engine, Depends(obter_engine)]

# Extensões que temos leitor para ler. Qualquer outra coisa é recusada antes de
# tocar o disco: o arquivo vem de fora e vai ser gravado, então a lista é de
# permissão, nunca de bloqueio.
EXTENSOES = frozenset({".ofx", ".qfx", ".csv", ".xlsx", ".pdf"})

# Extrato de um ano em PDF não passa de alguns MB. O limite existe para que um
# arquivo enorme não encha o disco antes de alguém perceber.
TAMANHO_MAXIMO = 10 * 1024 * 1024


def nome_seguro(enviado: str | None) -> str:
    """Só o nome do arquivo, sem nenhum componente de caminho.

    `Path(...).name` descarta '../' e qualquer diretório: o nome chega do cliente
    e não pode decidir ONDE o arquivo é gravado.
    """
    return Path(enviado or "extrato").name or "extrato"



class EntradaLancamento(BaseModel):
    descricao: str
    valor: str
    tipo: str = "despesa"
    data: date | None = None
    conta: str = "manual"
    categoria: str | None = None


class EntradaLote(BaseModel):
    padrao: str
    categoria: str
    criar_regra: bool = True


class EntradaDesfazer(BaseModel):
    fit_ids: list[str]
    padrao_da_regra: str | None = None


class EntradaConta(BaseModel):
    saldo_inicial: str


class EntradaCategoria(BaseModel):
    categoria: str | None


class EntradaRegra(BaseModel):
    padrao: str
    categoria: str
    tipo: str = "contem"
    prioridade: int = 100


class EntradaRecategorizar(BaseModel):
    reaplicar_tudo: bool = False



def criar_router() -> APIRouter:
    """Fábrica: chamada só dentro de criar_app, para não importar FastAPI na CLI."""
    router = APIRouter(tags=["financas"])

    @router.get("/resumo")
    def obter_resumo(engine: Motor) -> CardResumo:
        return resumo(engine)

    @router.get("/saldo")
    def obter_saldo(engine: Motor) -> dict[str, Any]:
        with engine.connect() as conn:
            centavos = int(
                conn.execute(text("SELECT saldo_centavos FROM vw_financas_saldo_v1")).scalar()
                or 0
            )
        return {"saldo_centavos": centavos, "saldo_formatado": Dinheiro(centavos).formatar()}

    @router.get("/fluxo-mensal")
    def obter_fluxo(engine: Motor) -> list[dict[str, object]]:
        return consultas.fluxo_mensal(engine)

    @router.get("/categorias")
    def obter_categorias(engine: Motor) -> list[dict[str, Any]]:
        repo = RepoTransacoesSQL(engine)
        return [
            {
                "categoria": nome,
                "total_centavos": total.centavos,
                "total_formatado": total.formatar(),
            }
            for nome, total in consultas.gastos_por_categoria(repo)
        ]

    @router.get("/gastos")
    def obter_gastos(
        engine: Motor, limite: Annotated[int, Query(ge=1, le=200)] = 10
    ) -> list[dict[str, Any]]:
        repo = RepoTransacoesSQL(engine)
        return [
            {
                "fit_id": t.fit_id,
                "data": t.data.isoformat(),
                "valor_centavos": t.valor.centavos,
                "valor_formatado": t.valor.formatar(),
                "descricao": t.descricao,
                "categoria": t.categoria,
            }
            for t in consultas.maiores_gastos(repo, limite)
        ]

    @router.get("/custo-basico")
    def obter_custo_basico(engine: Motor) -> analise.CustoBasico:
        return analise.custo_basico_mensal(engine)

    @router.get("/onde-cortar")
    def obter_onde_cortar(
        engine: Motor, limite: Annotated[int, Query(ge=1, le=50)] = 5
    ) -> list[analise.Corte]:
        return analise.onde_cortar(engine, limite)

    @router.get("/projecao")
    def obter_projecao(engine: Motor) -> analise.Projecao | None:
        # 200 com null, não 204: espelha a CLI ("nada a projetar") e mantém o
        # varredor de rotas podendo exigir 200 em todo GET.
        return analise.projecao_fim_do_mes(engine)

    @router.get("/sugestoes-de-regra")
    def obter_sugestoes(
        engine: Motor, limite: Annotated[int, Query(ge=1, le=50)] = 10
    ) -> list[sugestoes.SugestaoRegra]:
        return sugestoes.sugerir_regras(engine, limite)

    # ---------- escrita ----------
    # Nenhuma regra de negócio aqui: cada rota adapta HTTP para a MESMA função de
    # aplicacao/ que o comando de CLI chama. ValueError do domínio vira 422 com a
    # mensagem original — a borda não reescreve o que o domínio já explicou bem.

    @router.post("/lancamentos", status_code=201)
    def criar_lancamento(entrada: EntradaLancamento, engine: Motor) -> dict[str, Any]:
        try:
            resultado = escrita.lancar(
                RepoTransacoesSQL(engine),
                RepoRegrasSQL(engine),
                descricao=entrada.descricao,
                valor=entrada.valor,
                tipo=entrada.tipo,
                quando=entrada.data or date.today(),
                conta=entrada.conta,
                categoria=entrada.categoria,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        t = resultado.transacao
        return {
            "fit_id": t.fit_id,
            "data": t.data.isoformat(),
            "valor_centavos": t.valor.centavos,
            "valor_formatado": t.valor.formatar(),
            "descricao": t.descricao,
            "categoria": t.categoria,
            "inserida": resultado.inserida,
        }

    @router.post("/transacoes/categorizar-em-lote")
    def categorizar_em_lote(entrada: EntradaLote, engine: Motor) -> dict[str, Any]:
        try:
            resultado = escrita.categorizar_grupo(
                RepoTransacoesSQL(engine),
                RepoRegrasSQL(engine),
                padrao=entrada.padrao,
                categoria=entrada.categoria,
                criar_regra=entrada.criar_regra,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        return {"fit_ids": resultado.fit_ids, "regra_criada": resultado.regra_criada}

    @router.post("/transacoes/desfazer-lote")
    def desfazer_lote(entrada: EntradaDesfazer, engine: Motor) -> dict[str, int]:
        """Desfaz uma categorização em lote — categorias E a regra que a criou."""
        voltaram = escrita.desfazer_lote(
            RepoTransacoesSQL(engine),
            RepoRegrasSQL(engine),
            fit_ids=entrada.fit_ids,
            padrao_da_regra=entrada.padrao_da_regra,
        )
        return {"voltaram": voltaram}

    @router.patch("/transacoes/{fit_id}")
    def mudar_categoria(fit_id: str, entrada: EntradaCategoria, engine: Motor) -> dict[str, Any]:
        mudadas = RepoTransacoesSQL(engine).definir_categoria([fit_id], entrada.categoria)
        if mudadas == 0:
            raise HTTPException(status_code=404, detail=f"transação {fit_id} não existe")
        return {"fit_id": fit_id, "categoria": entrada.categoria}

    @router.put("/contas/{nome}")
    def definir_conta(nome: str, entrada: EntradaConta, engine: Motor) -> dict[str, Any]:
        try:
            valor = escrita.definir_saldo_conta(
                RepoContasSQL(engine), nome=nome, saldo_inicial=entrada.saldo_inicial
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        return {
            "nome": nome,
            "saldo_inicial_centavos": valor.centavos,
            "saldo_inicial_formatado": valor.formatar(),
        }

    @router.post("/regras", status_code=201)
    def criar_regra(entrada: EntradaRegra, engine: Motor) -> dict[str, Any]:
        try:
            criada = escrita.adicionar_regra(
                RepoRegrasSQL(engine),
                padrao=entrada.padrao,
                categoria=entrada.categoria,
                tipo=entrada.tipo,
                prioridade=entrada.prioridade,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        return {"padrao": entrada.padrao, "categoria": entrada.categoria, "criada": criada}

    @router.post("/recategorizar")
    def aplicar_regras(entrada: EntradaRecategorizar, engine: Motor) -> dict[str, int]:
        return {"mudadas": sugestoes.recategorizar(engine, entrada.reaplicar_tudo)}

    @router.post("/extratos", status_code=201)
    async def enviar_extratos(arquivos: list[UploadFile], engine: Motor) -> dict[str, Any]:
        """Recebe extratos, guarda em disco e importa. Dedup por fit_id."""
        destino = diretorio_extratos()
        destino.mkdir(parents=True, exist_ok=True)
        gravados: list[str] = []
        for enviado in arquivos:
            nome = nome_seguro(enviado.filename)
            if Path(nome).suffix.lower() not in EXTENSOES:
                raise HTTPException(
                    status_code=415,
                    detail=f"{nome}: formato não suportado (aceito: {', '.join(sorted(EXTENSOES))})",
                )
            conteudo = await enviado.read()
            if len(conteudo) > TAMANHO_MAXIMO:
                raise HTTPException(
                    status_code=413,
                    detail=f"{nome}: passa de {TAMANHO_MAXIMO // (1024 * 1024)} MB",
                )
            caminho = destino / nome
            caminho.write_bytes(conteudo)
            gravados.append(str(caminho))

        try:
            novas = importar_extratos(
                gravados, RepoTransacoesSQL(engine), RepoRegrasSQL(engine), detectar_leitor
            )
        except ValueError as e:
            # O leitor recusou (PDF que não reconcilia, por exemplo). O arquivo sai
            # do disco: guardar extrato que não pôde ser lido só acumula confusão.
            for caminho_gravado in gravados:
                Path(caminho_gravado).unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=str(e)) from e
        return {"novas": novas, "arquivos": [Path(c).name for c in gravados]}

    return router
