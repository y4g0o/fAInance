"""Apoio comum aos testes de HTTP."""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


ORIGEM = "http://127.0.0.1:8000"


def cliente_navegador(app: Any) -> TestClient:
    """TestClient que se comporta como o navegador real: loopback e `Origin`.

    Depois que a escrita passou a exigir origem (ADR 0009), cliente sem esse
    cabeçalho é recusado — corretamente. E desde a correção do DNS rebinding o
    Host também precisa ser de loopback, então o `testserver` padrão do
    TestClient não serve: ele simulava um host que o sistema nunca aceitaria.
    """
    return TestClient(app, base_url=ORIGEM, headers={"Origin": ORIGEM})
