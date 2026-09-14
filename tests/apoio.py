"""Apoio comum aos testes de HTTP."""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def cliente_navegador(app: Any) -> TestClient:
    """TestClient que se comporta como navegador, mandando `Origin`.

    Depois que a escrita passou a exigir origem (ADR 0009), cliente sem esse
    cabeçalho é recusado — corretamente. Todo teste que escreve precisa simular
    o navegador, que é o único cliente legítimo da API.
    """
    return TestClient(app, headers={"Origin": "http://testserver"})
