"""A SPA servida pelo próprio FastAPI, e a fronteira que a moldura não pode cruzar."""
from pathlib import Path

import pytest

from personalos.api.app import criar_app

from .apoio import cliente_navegador


@pytest.fixture
def cliente(tmp_path: Path):
    return cliente_navegador(criar_app(db=tmp_path / "spa.db"))


def test_spa_e_servida_em_app(cliente):
    """Um processo só: `personalos servir` entrega API e interface juntas."""
    r = cliente.get("/app/")

    assert r.status_code == 200
    assert "<div id=\"root\">" in r.text


def test_painel_jinja_continua_na_raiz(cliente):
    """A spec mantém o painel antigo vivo durante o P1 — montar a SPA não pode
    derrubar a única interface que hoje funciona."""
    assert cliente.get("/").status_code == 200


def test_a_moldura_da_spa_nao_conhece_nenhum_modulo():
    """Mesma regra do painel e da API (ADR 0006), agora no front: seção nova só
    entra por descoberta na API ou pelo registro da composição, nunca hardcoded
    na moldura. Sem isso, o segundo módulo obrigaria a reescrever o shell.
    """
    shell = Path(__file__).resolve().parents[1] / "web" / "src" / "shell"
    infratores = [
        arquivo.name
        for padrao in ("*.tsx", "*.ts", "*.css")
        for arquivo in shell.rglob(padrao)
        if "financas" in arquivo.read_text(encoding="utf-8").lower()
    ]

    assert infratores == [], f"moldura citando módulo: {infratores}"
