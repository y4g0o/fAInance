"""Aplicação FastAPI do PersonalOS: API JSON + painel, no mesmo processo.

Bind travado em loopback (ver `cli.servir`): não há autenticação, porque é um
sistema de um usuário na própria máquina.

Rotas do kernel moram aqui; cada módulo registrado contribui as suas via
`Modulo.criar_router`, montadas em `/api/<nome>`. O app não conhece módulo nenhum
por nome — é o que permite plugar biblioteca, saúde ou carro sem tocar neste arquivo.
"""
from __future__ import annotations

from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.engine import Engine

from personalos.api.dependencias import obter_chat, obter_engine
from personalos.api.origem import verificar_origem
from personalos.composicao import MODULOS, serie_mensal
from personalos.nucleo import insights as motor_insights
from personalos.nucleo import memoria as motor_memoria
from personalos.nucleo.portas.chat import ChatIndisponivel, Pergunta, Resposta, ServicoChat
from personalos.nucleo.sistema import criar_engine_do_sistema

Motor = Annotated[Engine, Depends(obter_engine)]
Chat = Annotated[ServicoChat | None, Depends(obter_chat)]


def criar_app(
    db: Path | None = None,
    chat: ServicoChat | None = None,
    modulos: tuple[Any, ...] | None = None,
    painel: bool = True,
    fluxo_mensal: Any = None,
) -> FastAPI:
    ativos = MODULOS if modulos is None else modulos
    fluxo_mensal = fluxo_mensal or serie_mensal
    app = FastAPI(title="PersonalOS", version=version("personalos"))
    app.state.engine = criar_engine_do_sistema(db)
    app.state.chat = chat
    app.middleware("http")(verificar_origem)

    @app.get("/api/saude")
    def saude() -> dict[str, Any]:
        return {"ok": True, "versao": app.version, "modulos": [m.nome for m in ativos]}

    @app.get("/api/insights")
    def listar_insights(
        engine: Motor, status: str | None = "novo", modulo: str | None = None
    ) -> list[dict[str, Any]]:
        encontrados = motor_insights.listar(
            engine, status=None if status == "todos" else status, modulo=modulo
        )
        return [
            {
                "id": i.id,
                "modulo": i.modulo,
                "regra_id": i.regra_id,
                "titulo": i.titulo,
                "detalhe": i.detalhe,
                "severidade": i.severidade,
                "status": i.status,
                "criado_em": i.criado_em,
            }
            for i in encontrados
        ]

    @app.patch("/api/insights/{insight_id}/status")
    def mudar_status(insight_id: int, novo: dict[str, str], engine: Motor) -> dict[str, Any]:
        status = novo.get("status", "")
        try:
            achou = motor_insights.definir_status(engine, insight_id, status)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        if not achou:
            raise HTTPException(status_code=404, detail=f"insight {insight_id} não existe")
        return {"id": insight_id, "status": status}

    @app.get("/api/memoria/fatos")
    def listar_fatos(
        engine: Motor, modulo: str | None = None, tipo: str | None = None
    ) -> list[dict[str, Any]]:
        return [
            {
                "modulo": f.modulo,
                "tipo": f.tipo,
                "chave": f.chave,
                "valor": f.valor,
                "atualizado_em": f.atualizado_em,
            }
            for f in motor_memoria.listar(engine, modulo=modulo, tipo=tipo)
        ]

    @app.post("/api/chat")
    def conversar(pergunta: dict[str, str], servico: Chat) -> Resposta:
        if servico is None:
            # 501, não 500: o contrato existe e está ligado; a implementação é a
            # fatia seguinte. O painel NÃO usa esta rota — ver painel/rotas.py.
            raise HTTPException(
                status_code=501,
                detail="Consultor em linguagem natural ainda não configurado.",
            )
        try:
            return servico.responder(Pergunta(texto=pergunta.get("texto", "")))
        except ChatIndisponivel as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

    for modulo in ativos:
        if modulo.criar_router is not None:
            app.include_router(modulo.criar_router(), prefix=f"/api/{modulo.nome}")

    if painel:
        from fastapi.staticfiles import StaticFiles

        from personalos.painel.rotas import RAIZ, criar_router as criar_painel

        app.mount("/static", StaticFiles(directory=str(RAIZ / "static")), name="static")

        # A SPA vive em /app enquanto o painel Jinja ocupa a raiz — a spec o mantém
        # vivo durante o P1, e derrubar a única interface que funciona para estrear
        # outra seria trocar o pneu com o carro andando.
        web_dist = Path(__file__).resolve().parents[1] / "web_dist"
        if web_dist.is_dir():
            app.mount("/app", StaticFiles(directory=str(web_dist), html=True), name="spa")
        # A fonte do fluxo é injetada: o painel não importa módulo nenhum, e é isso
        # que permite plugar biblioteca ou saúde sem tocar em painel/.
        app.include_router(criar_painel(tuple(ativos), fluxo_mensal))

    return app
