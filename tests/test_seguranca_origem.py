"""CSRF: escrita só é aceita quando vem da própria interface.

O painel roda sem autenticação em loopback, o que é seguro enquanto só lê. Com
escrita, qualquer site aberto no mesmo navegador pode disparar POST para
127.0.0.1:8000 — não lê a resposta, mas grava. O navegador não deixa um site
forjar `Origin`, então conferi-lo fecha o vetor sem exigir senha do usuário.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from personalos.api.app import criar_app

LANCAMENTO = {"descricao": "cafe", "valor": "7,50", "tipo": "despesa"}


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    return TestClient(criar_app(db=tmp_path / "seg.db"), base_url="http://127.0.0.1:8000")


def test_escrita_de_origem_estranha_e_recusada(cliente):
    r = cliente.post(
        "/api/financas/lancamentos", json=LANCAMENTO, headers={"Origin": "https://site-malicioso.com"}
    )

    assert r.status_code == 403


def test_escrita_sem_origem_e_recusada(cliente):
    """Sem Origin também recusa: a CLI fala com o banco direto, não com o HTTP,
    então não há cliente legítimo sem navegador para proteger."""
    r = cliente.post("/api/financas/lancamentos", json=LANCAMENTO)

    assert r.status_code == 403


def test_escrita_da_propria_interface_passa(cliente):
    r = cliente.post(
        "/api/financas/lancamentos", json=LANCAMENTO, headers={"Origin": "http://127.0.0.1:8000"}
    )

    assert r.status_code == 201


def test_leitura_nao_e_afetada(cliente):
    """GET não muda estado; exigir Origin nele só quebraria abrir a página."""
    assert cliente.get("/api/saude").status_code == 200
