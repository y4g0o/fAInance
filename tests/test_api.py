"""API JSON — banco vazio, banco semeado, e paridade com a camada de aplicação.

Nenhum teste toca o banco real: todos usam tmp_path com dados sintéticos.
"""
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from .apoio import cliente_navegador

from personalos.api.app import criar_app
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoTransacoesSQL
from personalos.nucleo.portas.chat import Pergunta, Resposta

SEMEADO = [
    Transacao("s1", date(2026, 6, 1), Dinheiro(500000), "SALARIO", "conta"),
    Transacao("a1", date(2026, 6, 5), Dinheiro(-120000), "ALUGUEL 06/26", "conta"),
    Transacao("a2", date(2026, 7, 5), Dinheiro(-120000), "ALUGUEL 07/26", "conta", "Moradia"),
    Transacao("s2", date(2026, 7, 1), Dinheiro(500000), "SALARIO", "conta"),
]


@pytest.fixture
def cliente_vazio(tmp_path: Path) -> TestClient:
    return cliente_navegador(criar_app(db=tmp_path / "vazio.db"))


@pytest.fixture
def cliente_semeado(tmp_path: Path) -> TestClient:
    app = criar_app(db=tmp_path / "cheio.db")
    RepoTransacoesSQL(app.state.engine).inserir_muitas(SEMEADO)
    return cliente_navegador(app)


def _gets_sem_parametro(app) -> list[str]:
    """Lista as rotas GET a partir do esquema OpenAPI, não de `app.routes`.

    Motivo, descoberto quando este varredor achou 3 rotas em vez de 12: nesta versão
    do FastAPI, `include_router` guarda um objeto aninhado em `app.routes` em vez de
    achatar as rotas, então iterar `app.routes` perde tudo que vem de módulo — e o
    varredor daria falso verde justamente sobre o código novo. O OpenAPI é a fonte
    autoritativa e não depende da representação interna.
    """
    return sorted(
        caminho
        for caminho, metodos in app.openapi()["paths"].items()
        if "get" in metodos and "{" not in caminho
    )


# ---------- o teste que carrega a fatia ----------


def test_toda_rota_get_responde_200_em_banco_vazio(tmp_path):
    """Auto-extensível de propósito: um endpoint novo que quebre em banco vazio
    (view faltando, mediana de lista vazia, scalar_one sem linha) falha aqui SEM
    ninguém editar o teste. Banco vazio é o estado de toda instalação nova."""
    app = criar_app(db=tmp_path / "vazio.db")
    cliente = cliente_navegador(app)
    rotas = _gets_sem_parametro(app)
    assert len(rotas) >= 10, "o varredor precisa estar realmente encontrando rotas"
    for rota in rotas:
        assert cliente.get(rota).status_code == 200, f"{rota} quebrou em banco vazio"


def test_toda_rota_get_responde_200_em_banco_semeado(cliente_semeado):
    app = cliente_semeado.app
    for rota in _gets_sem_parametro(app):
        assert cliente_semeado.get(rota).status_code == 200, f"{rota} quebrou com dados"


# ---------- kernel ----------


def test_saude_lista_os_modulos_ativos(cliente_vazio):
    corpo = cliente_vazio.get("/api/saude").json()
    assert corpo["ok"] is True
    assert "financas" in corpo["modulos"]


def test_openapi_documenta_as_rotas_do_modulo(cliente_vazio):
    caminhos = cliente_vazio.get("/openapi.json").json()["paths"]
    assert "/api/financas/resumo" in caminhos
    assert "/api/financas/custo-basico" in caminhos


def test_projecao_sem_movimento_devolve_200_com_null(cliente_vazio):
    """200 com null, não 204: espelha a CLI e mantém o varredor podendo exigir 200."""
    resposta = cliente_vazio.get("/api/financas/projecao")
    assert resposta.status_code == 200
    assert resposta.json() is None


# ---------- card ----------


def test_resumo_de_banco_vazio_avisa_em_vez_de_zerar(cliente_vazio):
    corpo = cliente_vazio.get("/api/financas/resumo").json()
    assert corpo["vazio"] is True
    assert corpo["metricas"] == []
    assert "importar" in corpo["aviso"]


def test_resumo_com_dados_traz_metrica_formatada(cliente_semeado):
    corpo = cliente_semeado.get("/api/financas/resumo").json()
    assert corpo["vazio"] is False
    assert corpo["metricas"][0]["rotulo"] == "Saldo"
    assert corpo["metricas"][0]["valor"].startswith("R$")


# ---------- paridade: a API não pode reimplementar aritmética ----------


def test_saldo_da_api_bate_com_a_view(cliente_semeado):
    from sqlalchemy import text

    engine = cliente_semeado.app.state.engine
    with engine.connect() as conn:
        da_view = conn.execute(text("SELECT saldo_centavos FROM vw_financas_saldo_v1")).scalar()
    assert cliente_semeado.get("/api/financas/saldo").json()["saldo_centavos"] == da_view


def test_custo_basico_da_api_bate_campo_a_campo(cliente_semeado):
    from personalos.modulos.financas.aplicacao.analise import custo_basico_mensal

    esperado = custo_basico_mensal(cliente_semeado.app.state.engine)
    corpo = cliente_semeado.get("/api/financas/custo-basico").json()
    assert corpo["total_centavos"] == esperado.total_centavos
    assert corpo["fixos_centavos"] == esperado.fixos_centavos
    assert corpo["meses_considerados"] == esperado.meses_considerados


# ---------- convenção de sinal, no limite HTTP ----------


def test_convencao_de_sinal_sobrevive_a_serializacao(cliente_semeado):
    """Regra do ADR 0004: valor_centavos com sinal do ledger, agregado de despesa
    como magnitude positiva, valor líquido com sinal."""
    fluxo = cliente_semeado.get("/api/financas/fluxo-mensal").json()
    junho = next(m for m in fluxo if m["mes"] == "2026-06")
    assert junho["despesas_centavos"] > 0  # magnitude
    assert junho["resultado_centavos"] == junho["receitas_centavos"] - junho["despesas_centavos"]
    for gasto in cliente_semeado.get("/api/financas/gastos").json():
        assert gasto["valor_centavos"] < 0  # ledger


def test_nenhum_campo_de_centavos_vem_como_float(cliente_semeado):
    """Dinheiro é int em centavos, sempre. Float em dinheiro é bug esperando data."""
    for rota in _gets_sem_parametro(cliente_semeado.app):
        corpo = cliente_semeado.get(rota).json()
        for chave, valor in _pares(corpo):
            if chave.endswith("_centavos"):
                assert not isinstance(valor, float), f"{rota}: {chave} veio float"


def _pares(no, prefixo=""):
    if isinstance(no, dict):
        for chave, valor in no.items():
            yield chave, valor
            yield from _pares(valor, chave)
    elif isinstance(no, list):
        for item in no:
            yield from _pares(item, prefixo)


# ---------- insights ----------


def test_dispensar_insight_muda_o_banco(cliente_semeado):
    """Dispensar pelo HTTP tem de mudar a linha, não só devolver 200."""
    from personalos.nucleo import insights as motor
    from personalos.nucleo.modulo import Insight, Modulo, RegraInsight

    engine = cliente_semeado.app.state.engine
    regra = RegraInsight("teste", lambda _e: [Insight("k", "algo fora do normal")])
    modulo = Modulo(nome="financas", metadata=None, regras_insights=(regra,))  # type: ignore[arg-type]
    motor.gerar(engine, (modulo,))

    antes = cliente_semeado.get("/api/insights").json()
    assert len(antes) == 1
    alvo = antes[0]["id"]

    resposta = cliente_semeado.patch(
        f"/api/insights/{alvo}/status", json={"status": "dispensado"}
    )
    assert resposta.status_code == 200
    assert cliente_semeado.get("/api/insights").json() == []  # sumiu dos novos
    assert [i.id for i in motor.listar(engine, status="dispensado")] == [alvo]


def test_dispensar_insight_inexistente_da_404(cliente_semeado):
    resposta = cliente_semeado.patch("/api/insights/999/status", json={"status": "visto"})
    assert resposta.status_code == 404


def test_status_invalido_da_422(cliente_semeado):
    resposta = cliente_semeado.patch("/api/insights/1/status", json={"status": "arquivado"})
    assert resposta.status_code == 422


# ---------- porta de chat ----------


def test_chat_sem_servico_da_501_explicando(cliente_vazio):
    resposta = cliente_vazio.post("/api/chat", json={"texto": "quanto gastei?"})
    assert resposta.status_code == 501
    assert "não configurado" in resposta.json()["detail"]


def test_chat_com_servico_injetado_responde_200(tmp_path):
    """Prova que a porta está ligada e não é código morto — a justificativa da spec
    para ela existir antes do consultor."""

    class ChatFalso:
        def responder(self, pergunta: Pergunta) -> Resposta:
            return Resposta(texto=f"eco: {pergunta.texto}", ferramentas=("nenhuma",))

    cliente = cliente_navegador(criar_app(db=tmp_path / "t.db", chat=ChatFalso()))
    corpo = cliente.post("/api/chat", json={"texto": "oi"}).json()
    assert corpo["texto"] == "eco: oi"
    assert corpo["degradado"] is False
    assert corpo["ferramentas"] == ["nenhuma"]


# ---------- independência de módulos ----------


def test_app_sem_modulo_nenhum_ainda_sobe(tmp_path):
    """O kernel não pode depender de haver módulo: é o que permite plugar e
    desplugar módulo sem tocar no app."""
    cliente = cliente_navegador(criar_app(db=tmp_path / "t.db", modulos=()))
    assert cliente.get("/api/saude").json()["modulos"] == []
    assert cliente.get("/api/financas/resumo").status_code == 404


# ---------- comando servir ----------


def test_servir_recusa_bind_fora_de_loopback():
    """Sem escape hatch de propósito: uma flag '--eu-sei-o-que-estou-fazendo' seria o
    caminho mais curto para publicar a vida financeira na rede local sem perceber."""
    import typer

    from personalos.cli import _validar_host

    _validar_host("127.0.0.1")  # não levanta
    _validar_host("localhost")
    for host in ("0.0.0.0", "192.168.0.10", "::"):
        with pytest.raises(typer.BadParameter, match="autenticação"):
            _validar_host(host)


def test_servir_aparece_no_help_da_cli():
    from typer.testing import CliRunner

    from personalos.cli import app as raiz

    saida = CliRunner().invoke(raiz, ["--help"]).stdout
    assert "servir" in saida


def test_camada_web_nao_conhece_nenhum_modulo():
    """A mesma regra que o painel já tinha, agora também para api/.

    A revisão encontrou `api/app.py` importando financas pelo nome para alimentar o
    gráfico — o painel estava limpo e a API não. Saber QUAL módulo fornece o quê é
    conhecimento de composição, e mora em `composicao.py`.
    """
    import personalos.api as pacote

    raiz = Path(pacote.__file__).parent
    infratores = [
        arquivo.name
        for arquivo in raiz.rglob("*.py")
        if "personalos.modulos" in arquivo.read_text(encoding="utf-8")
    ]
    assert infratores == [], f"camada web citando módulo: {infratores}"
