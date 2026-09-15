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
from personalos.modulos.financas.aplicacao.escrita import reprocessar_insights
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


# Ler em pedaços de 1 MB: o limite precisa valer DURANTE a leitura.
PEDACO = 1024 * 1024


def caminho_livre(destino: Path, nome: str, conteudo: bytes) -> Path:
    """Onde gravar sem apagar arquivo anterior de mesmo nome.

    Os extratos originais são a recuperação de desastre. Reenviar o MESMO
    arquivo é o caso comum e pode sobrescrever à vontade; conteúdo diferente com
    o mesmo nome ganha sufixo, porque apagar a cópia boa em silêncio é perda de
    dado que ninguém percebe.
    """
    caminho = destino / nome
    if not caminho.exists() or caminho.read_bytes() == conteudo:
        return caminho
    base, sufixo = caminho.stem, caminho.suffix
    n = 2
    while (alternativo := destino / f"{base}-{n}{sufixo}").exists():
        if alternativo.read_bytes() == conteudo:
            return alternativo
        n += 1
    return alternativo


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


class EntradaRenomear(BaseModel):
    de: str
    para: str


class EntradaNaoConsumo(BaseModel):
    e_movimentacao: bool = True


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
            for nome, total in consultas.gastos_por_categoria(
                repo, nao_consumo=escrita.categorias_nao_consumo(engine)
            )
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
    ) -> list[dict[str, Any]]:
        """Grupos sem categoria, com a categoria que o histórico do usuário sugere.

        A sugestão carrega a evidência (`sugerida_por`, `sugestao_transacoes`):
        sugestão sem justificativa é adivinhação com cara de autoridade.
        """
        resultado = []
        for g in sugestoes.sugerir_regras(engine, limite):
            sugestao = sugestoes.sugerir_categoria(engine, g.exemplo)
            resultado.append(
                {
                    "padrao": g.padrao,
                    "exemplo": g.exemplo,
                    "ocorrencias": g.ocorrencias,
                    "total_centavos": g.total_centavos,
                    "alcance": g.alcance,
                    "categoria_sugerida": sugestao.categoria if sugestao else None,
                    "sugerida_por": sugestao.palavra if sugestao else None,
                    "sugestao_transacoes": sugestao.transacoes if sugestao else 0,
                }
            )
        return resultado

    @router.get("/categorias-usadas")
    def obter_categorias_usadas(engine: Motor) -> list[str]:
        """As categorias que já existem — para a tela oferecer em vez de pedir
        que o usuário digite de novo e crie 'compras' ao lado de 'Compras'."""
        with engine.connect() as conn:
            linhas = conn.execute(
                text(
                    "SELECT DISTINCT categoria FROM financas_transacoes "
                    "WHERE categoria IS NOT NULL AND categoria <> '' ORDER BY categoria"
                )
            ).all()
        return [str(linha.categoria) for linha in linhas]

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
                RepoContasSQL(engine),
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
        # 0o700: extrato bancário não pode ficar legível para outros usuários da
        # máquina. O banco e os backups já eram assim; esta pasta nascia com o
        # umask padrão (775) — achado na revisão de segurança.
        destino.mkdir(parents=True, exist_ok=True, mode=0o700)
        destino.chmod(0o700)
        gravados: list[str] = []
        for enviado in arquivos:
            nome = nome_seguro(enviado.filename)
            if Path(nome).suffix.lower() not in EXTENSOES:
                raise HTTPException(
                    status_code=415,
                    detail=f"{nome}: formato não suportado (aceito: {', '.join(sorted(EXTENSOES))})",
                )
            # Lê em pedaços e para no limite: `read()` inteiro bufferiza o arquivo
            # ANTES de conferir o tamanho, então o limite não protegia de nada.
            partes: list[bytes] = []
            lidos = 0
            while pedaco := await enviado.read(PEDACO):
                lidos += len(pedaco)
                if lidos > TAMANHO_MAXIMO:
                    raise HTTPException(
                        status_code=413,
                        detail=f"{nome}: passa de {TAMANHO_MAXIMO // (1024 * 1024)} MB",
                    )
                partes.append(pedaco)
            conteudo = b"".join(partes)

            caminho = caminho_livre(destino, nome, conteudo)
            caminho.write_bytes(conteudo)
            caminho.chmod(0o600)
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
        # Mesma coisa que `financas importar` faz ao fim: sem isto, quem usa a
        # tela para de receber alerta e não tem como perceber.
        alertas = reprocessar_insights(engine)
        return {
            "novas": novas,
            "arquivos": [Path(c).name for c in gravados],
            "alertas_novos": alertas,
        }

    # ---------- o que o sistema aprendeu, e como discordar ----------

    @router.get("/pode-comprar")
    def simular_compra(
        engine: Motor,
        valor_centavos: Annotated[int, Query(ge=1)],
        parcelas: Annotated[int, Query(ge=1, le=120)] = 1,
        taxa_mensal: Annotated[float, Query(ge=0, le=1)] = 0.0,
        parcela_centavos: Annotated[int | None, Query(ge=1)] = None,
    ) -> analise.Compra:
        """Os números de uma compra — sem veredito. A decisão é do usuário.

        Informar o valor da parcela revela a taxa embutida: é assim que se
        descobre que o "10x sem juros" tem juro.
        """
        try:
            return analise.pode_comprar(
                engine, valor_centavos, parcelas, taxa_mensal, parcela_centavos
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    @router.get("/fixos")
    def listar_fixos(engine: Motor) -> list[dict[str, Any]]:
        """Gastos fixos aprendidos. A tela precisa MOSTRAR isto: hoje o usuário só
        descobre o que o sistema aprendeu quando um alerta estranho aparece."""
        from personalos.modulos.financas.insights import gastos_fixos_conhecidos

        return [
            {
                "chave": f.chave,
                "descricao_exemplo": f.descricao_exemplo,
                "valor_mediano_centavos": f.valor_mediano_centavos,
                "valor_mediano_formatado": Dinheiro(f.valor_mediano_centavos).formatar(),
                "meses": len(f.meses),
                "ultima_data": f.ultima_data,
            }
            for f in gastos_fixos_conhecidos(engine)
        ]

    @router.post("/fixos/{chave}/esquecer")
    def esquecer_fixo(chave: str, engine: Motor) -> dict[str, Any]:
        """Esquece E registra que não deve voltar — sem isso a correção dura até
        a próxima importação."""
        from personalos.modulos.financas.insights import esquecer_fixo as esquecer

        return {"chave": chave, "existia": esquecer(engine, chave)}

    @router.post("/categorias/renomear")
    def renomear_categoria(entrada: EntradaRenomear, engine: Motor) -> dict[str, int]:
        try:
            mudadas = escrita.renomear_categoria(
                RepoTransacoesSQL(engine), de=entrada.de, para=entrada.para
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        return {"mudadas": mudadas}

    @router.post("/categorias/{nome}/nao-consumo")
    def marcar_nao_consumo(nome: str, entrada: EntradaNaoConsumo, engine: Motor) -> dict[str, Any]:
        """Declara que a categoria MOVE dinheiro em vez de consumi-lo.

        Declarar errado ESCONDE gasto, então é explícito e nunca inferido.
        """
        escrita.declarar_nao_consumo(engine, nome, e_movimentacao=entrada.e_movimentacao)
        return {"categoria": nome, "e_movimentacao": entrada.e_movimentacao}

    @router.get("/categorias-nao-consumo")
    def listar_nao_consumo(engine: Motor) -> list[str]:
        return sorted(escrita.categorias_nao_consumo(engine))

    return router
