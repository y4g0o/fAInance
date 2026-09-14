"""Rotas do painel. Sem JavaScript: formulário HTML puro e SVG do servidor.

Âncoras de id que os testes podem usar como contrato (mudar exige mudar o teste):
`secao-resumo`, `secao-graficos`, `secao-pergunta`, `secao-insights`,
`lista-insights`, `secao-primeiro-uso`.

Assimetria proposital com a API: `POST /api/chat` devolve 501 quando não há
consultor (contrato de dados correto), mas aqui a mesma situação devolve 200 com a
página e um aviso — uma página de erro no navegador não ajuda ninguém.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from jinja2 import StrictUndefined

from personalos.api.dependencias import obter_chat, obter_engine
from personalos.nucleo import insights as motor_insights
from sqlalchemy.engine import Engine

from personalos.nucleo.modulo import Modulo
from personalos.nucleo.portas.chat import ChatIndisponivel, Pergunta
from personalos.painel import grafico
from personalos.painel.contexto import montar_contexto

RAIZ = Path(__file__).parent
templates = Jinja2Templates(directory=str(RAIZ / "templates"))
# StrictUndefined: variável com typo LEVANTA em vez de renderizar vazio, então o
# smoke de "a rota devolve 200" já cobre erro de template.
templates.env.undefined = StrictUndefined


# `Any` no valor é honesto: a linha vem do SQL, e o painel converte na hora de
# desenhar. Fingir um tipo mais estreito aqui só empurraria casts para o chamador.
FonteDeSerie = Callable[[Engine], Sequence[Mapping[str, Any]]]


def criar_router(modulos: Sequence[Modulo], fluxo_de: FonteDeSerie) -> APIRouter:
    """`fluxo_de` devolve a série mensal do gráfico.

    É injetada (e não importada) para o painel não conhecer módulo nenhum — quem
    sabe qual módulo fornece o gráfico é o composition root.
    """
    router = APIRouter(include_in_schema=False)

    def _render(request: Request, resposta: str | None = None) -> Response:
        engine = obter_engine(request)
        chat = obter_chat(request)
        fluxo = fluxo_de(engine)
        ctx = montar_contexto(engine, modulos, chat is not None, fluxo)
        svg = grafico.barras(
            [str(m["mes"]) for m in fluxo],
            [
                grafico.Serie("receitas", [int(m["receitas_centavos"]) for m in fluxo], "receitas"),
                grafico.Serie("despesas", [int(m["despesas_centavos"]) for m in fluxo], "despesas"),
            ],
        ) if ctx.tem_grafico else ""
        return templates.TemplateResponse(
            request, "painel.html", {"ctx": ctx, "grafico": svg, "resposta": resposta}
        )

    @router.get("/", response_class=HTMLResponse)
    def painel(request: Request) -> Response:
        return _render(request)

    @router.post("/painel/insights/{insight_id}/dispensar")
    def dispensar(request: Request, insight_id: int) -> Response:
        motor_insights.definir_status(obter_engine(request), insight_id, "dispensado")
        # 303: redireciona para GET, para F5 não repetir o POST.
        return RedirectResponse("/", status_code=303)

    @router.post("/painel/perguntar", response_class=HTMLResponse)
    async def perguntar(request: Request) -> Response:
        # Parse manual em vez de Form()/request.form(): AMBOS exigem a dependência
        # python-multipart nesta versão do Starlette (o assert vem antes de olhar o
        # content-type, verificado). Um formulário de um campo é urlencoded, e
        # decodificá-lo é uma linha de stdlib — não vale uma dependência por dez anos.
        corpo = (await request.body()).decode("utf-8")
        texto = parse_qs(corpo).get("texto", [""])[0]
        chat = obter_chat(request)
        if chat is None:
            return _render(request)
        try:
            return _render(request, chat.responder(Pergunta(texto=texto)).texto)
        except ChatIndisponivel as e:
            return _render(request, f"Indisponível: {e}")

    return router
