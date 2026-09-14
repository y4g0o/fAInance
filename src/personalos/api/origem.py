"""Verificação de origem: a defesa de CSRF de um painel sem autenticação.

O PersonalOS não pede senha porque é um usuário só, na própria máquina, em
loopback. Isso é seguro enquanto a API só lê. Com escrita aparece um vetor real:
qualquer site aberto no mesmo navegador pode disparar POST para 127.0.0.1:8000.
Ele não consegue LER a resposta (a política de mesma origem impede), mas
consegue GRAVAR — apagar categorias, inserir lançamentos, bagunçar o banco.

`Origin` é o cabeçalho que o navegador preenche sozinho e que uma página não
consegue forjar. Conferi-lo fecha o vetor sem custar nada ao usuário: ele
continua abrindo localhost e usando, sem login.

Requisição sem `Origin` também é recusada. Não há cliente legítimo sem navegador
a proteger: a CLI fala com o banco direto, nunca com o HTTP.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

METODOS_QUE_ESCREVEM = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def origem_permitida(origem: str | None, host: str | None) -> bool:
    """Aceita apenas a origem servida por este próprio processo."""
    if not origem or not host:
        return False
    return origem in (f"http://{host}", f"https://{host}")


async def verificar_origem(
    request: Request, proxima: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.method in METODOS_QUE_ESCREVEM and not origem_permitida(
        request.headers.get("origin"), request.headers.get("host")
    ):
        return JSONResponse(
            status_code=403,
            content={
                "detail": (
                    "Escrita recusada: a requisição não veio desta interface. "
                    "Abra o PersonalOS em http://127.0.0.1:8000 e tente por lá."
                )
            },
        )
    return await proxima(request)
