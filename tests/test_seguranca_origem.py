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


def test_host_forjado_nao_autoriza_escrita(cliente):
    """DNS rebinding: um site cujo domínio resolve para 127.0.0.1 faz o navegador
    enviar Host E Origin dele mesmo. Comparar um com o outro não protege nada —
    os dois são do atacante.

    Verificado contra o servidor real antes do conserto: a requisição respondeu
    201 e GRAVOU uma transação no banco.
    """
    r = cliente.post(
        "/api/financas/lancamentos",
        json=LANCAMENTO,
        headers={"Host": "site-malicioso.com:8000", "Origin": "http://site-malicioso.com:8000"},
    )

    assert r.status_code == 403


def test_host_de_loopback_com_porta_continua_valendo(cliente):
    """O uso normal não pode quebrar: localhost e 127.0.0.1, com ou sem porta."""
    for host, origem in [
        ("127.0.0.1:8000", "http://127.0.0.1:8000"),
        ("localhost:8000", "http://localhost:8000"),
        ("127.0.0.1", "http://127.0.0.1"),
    ]:
        r = cliente.post(
            "/api/financas/lancamentos", json=LANCAMENTO, headers={"Host": host, "Origin": origem}
        )
        assert r.status_code == 201, f"uso legítimo recusado: {host}"
