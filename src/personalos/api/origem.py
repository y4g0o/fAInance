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

# O servidor só aceita bind em loopback (`cli._validar_host`), então qualquer
# outro Host é forjado. Esta lista não é conveniência: é o que impede DNS
# rebinding.
HOSTS_DE_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


def _sem_porta(host: str) -> str:
    """Tira a porta de 'host:porta', respeitando IPv6 em colchetes."""
    if host.startswith("["):
        return host.split("]")[0] + "]"
    return host.split(":")[0]


def origem_permitida(origem: str | None, host: str | None) -> bool:
    """Aceita escrita apenas da interface servida por este próprio processo.

    Confere o HOST contra uma lista fixa antes de qualquer coisa. A versão
    anterior comparava Origin com Host — e num ataque de DNS rebinding os DOIS
    são do atacante: um domínio dele resolve para 127.0.0.1, o navegador envia
    Host e Origin desse domínio, e a comparação fecha.

    Foi verificado contra o servidor real: a requisição respondia 201 e gravava.
    """
    if not origem or not host:
        return False
    if _sem_porta(host) not in HOSTS_DE_LOOPBACK:
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
