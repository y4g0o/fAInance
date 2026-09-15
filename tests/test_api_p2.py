"""Endpoints que as telas de análise precisam e ainda não existiam."""
from datetime import date
from pathlib import Path

import pytest

from personalos.api.app import criar_app
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoTransacoesSQL
from personalos.modulos.financas.insights import aprender_gastos_fixos

from .apoio import cliente_navegador


@pytest.fixture
def cliente(tmp_path: Path):
    app = criar_app(db=tmp_path / "p2.db")
    RepoTransacoesSQL(app.state.engine).inserir_muitas(
        [
            Transacao(f"a{m}", date(2026, m, 10), Dinheiro(-5611), f"ASSINATURA {m:02d}", "conta", "Serviços")
            for m in (5, 6, 7)
        ]
    )
    # O aprendizado roda ao importar; o GET só lista o que já é conhecido —
    # requisição de leitura que grava é armadilha.
    aprender_gastos_fixos(app.state.engine, hoje=date(2026, 7, 20))
    return app, cliente_navegador(app)


def test_lista_os_gastos_fixos_aprendidos(cliente):
    """A tela precisa MOSTRAR o que o sistema aprendeu — hoje o usuário só
    descobre quando um alerta estranho aparece."""
    _, api = cliente

    r = api.get("/api/financas/fixos")

    assert r.status_code == 200
    assert any("assinatura" in f["chave"] for f in r.json())


def test_esquecer_fixo_pela_api_e_ele_nao_volta(cliente):
    """`esquecer-fixo` só existia no terminal — e o princípio do projeto é que
    nenhuma tarefa rotineira exija terminal."""
    _, api = cliente
    chave = next(f["chave"] for f in api.get("/api/financas/fixos").json())

    r = api.post(f"/api/financas/fixos/{chave}/esquecer")

    assert r.status_code == 200
    assert all(f["chave"] != chave for f in api.get("/api/financas/fixos").json())


def test_declarar_categoria_como_movimentacao(cliente):
    _, api = cliente

    r = api.post("/api/financas/categorias/Serviços/nao-consumo", json={"e_movimentacao": True})

    assert r.status_code == 200
    assert "Serviços" in api.get("/api/financas/categorias-nao-consumo").json()


def test_renomear_categoria_pela_api(cliente):
    _, api = cliente

    r = api.post("/api/financas/categorias/renomear", json={"de": "Serviços", "para": "Assinaturas"})

    assert r.status_code == 200
    assert r.json()["mudadas"] == 3


def test_lista_categorias_existentes_para_o_seletor(cliente):
    """O campo de categoria é texto livre e por isso nasceram 'compras' e
    'Compras' como fatias diferentes. A tela precisa oferecer o que já existe."""
    _, api = cliente

    r = api.get("/api/financas/categorias-usadas")

    assert r.status_code == 200
    assert "Serviços" in r.json()


def test_sugestoes_de_regra_trazem_a_categoria_sugerida(cliente):
    """Sugestão vem do histórico do próprio usuário, com a evidência junto."""
    app, api = cliente
    RepoTransacoesSQL(app.state.engine).inserir_muitas(
        # duas: o agrupador exige repetição, senão não é grupo
        [
            Transacao("n1", date(2026, 8, 1), Dinheiro(-2000), "ASSINATURA NOVA MENSAL", "conta"),
            Transacao("n2", date(2026, 9, 1), Dinheiro(-2000), "ASSINATURA NOVA MENSAL", "conta"),
        ]
    )

    grupos = api.get("/api/financas/sugestoes-de-regra?limite=10").json()
    alvo = next(g for g in grupos if "assinatura" in g["exemplo"].lower())

    assert alvo["categoria_sugerida"] == "Serviços"
    assert alvo["sugerida_por"] == "assinatura"


def test_simulador_de_compra_devolve_os_numeros_sem_veredito(cliente):
    """`pode-comprar` existia só no terminal. Ele não julga: devolve parcela,
    juro embutido, folga e meses de reserva — a decisão é do usuário."""
    _, api = cliente

    r = api.get("/api/financas/pode-comprar?valor_centavos=450000&parcelas=10&parcela_centavos=50000")

    assert r.status_code == 200
    corpo = r.json()
    assert corpo["parcela_centavos"] == 50000
    assert corpo["juros_centavos"] == 50000 * 10 - 450000
    assert corpo["taxa_mensal"] > 0  # o "sem juros" que tem juros


def test_simulador_recusa_valor_invalido(cliente):
    _, api = cliente

    assert api.get("/api/financas/pode-comprar?valor_centavos=0").status_code == 422
