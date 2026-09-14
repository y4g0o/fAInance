"""Painel — três camadas, com orçamento de fragilidade.

1. A maioria dos testes bate em `montar_contexto` e `grafico.barras`: funções puras,
   sem HTML e sem HTTP. É onde toda a lógica vive.
2. Poucos smokes de rota (200 + text/html + saída sem marca de template quebrado).
   Funcionam porque o Jinja usa StrictUndefined: typo em variável LEVANTA.
3. No máximo 6 asserções de string em HTML na suíte inteira, e só sobre âncoras
   `id=` declaradas como contrato no docstring de `painel/rotas.py`.
   Contagem atual: 4 (secao-resumo, secao-graficos, secao-insights, lista-insights).

Proibido: asserção sobre texto de copy, classe CSS, aninhamento de tags ou ordem de
atributos — é o que torna teste de HTML insuportável de manter.
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
from personalos.nucleo.modulo import Modulo
from personalos.painel import grafico
from personalos.painel.contexto import montar_contexto

SEMEADO = [
    Transacao("s1", date(2026, 6, 1), Dinheiro(500000), "SALARIO", "conta"),
    Transacao("a1", date(2026, 6, 5), Dinheiro(-120000), "ALUGUEL 06", "conta"),
    Transacao("s2", date(2026, 7, 1), Dinheiro(500000), "SALARIO", "conta"),
    Transacao("a2", date(2026, 7, 5), Dinheiro(-130000), "ALUGUEL 07", "conta"),
]


@pytest.fixture
def cliente_semeado(tmp_path: Path) -> TestClient:
    app = criar_app(db=tmp_path / "cheio.db")
    RepoTransacoesSQL(app.state.engine).inserir_muitas(SEMEADO)
    return cliente_navegador(app)


@pytest.fixture
def cliente_vazio(tmp_path: Path) -> TestClient:
    return cliente_navegador(criar_app(db=tmp_path / "vazio.db"))


# ---------- camada 1: contexto, função pura ----------


def test_contexto_de_banco_vazio_e_primeiro_uso(tmp_path):
    app = criar_app(db=tmp_path / "v.db", painel=False)
    ctx = montar_contexto(app.state.engine, tuple(_modulos_de(app)))
    assert ctx.primeiro_uso is True
    assert ctx.tem_grafico is False and ctx.tem_insights is False
    assert all(c.vazio for c in ctx.cards)


def test_contexto_com_dados_nao_e_primeiro_uso(cliente_semeado):
    ctx = montar_contexto(
        cliente_semeado.app.state.engine, tuple(_modulos_de(cliente_semeado.app))
    )
    assert ctx.primeiro_uso is False
    assert len(ctx.cards) == 1


def test_grafico_so_aparece_com_dois_meses(cliente_semeado):
    engine = cliente_semeado.app.state.engine
    modulos = tuple(_modulos_de(cliente_semeado.app))
    um_mes = [{"mes": "2026-06", "receitas_centavos": 1, "despesas_centavos": 1}]
    assert montar_contexto(engine, modulos, fluxo=um_mes).tem_grafico is False
    assert montar_contexto(engine, modulos, fluxo=um_mes * 2).tem_grafico is True


def test_chat_indisponivel_por_padrao(cliente_semeado):
    ctx = montar_contexto(
        cliente_semeado.app.state.engine, tuple(_modulos_de(cliente_semeado.app))
    )
    assert ctx.chat_disponivel is False


def test_modulo_sem_card_nao_entra_no_resumo(tmp_path):
    app = criar_app(db=tmp_path / "v.db", painel=False)
    sem_card = Modulo(nome="x", metadata=None)  # type: ignore[arg-type]
    assert montar_contexto(app.state.engine, (sem_card,)).cards == ()


def _modulos_de(app):
    from personalos.composicao import MODULOS

    return MODULOS


# ---------- camada 1: gráfico, função pura ----------


def test_grafico_desenha_uma_barra_por_mes_e_serie():
    svg = grafico.barras(
        ["2026-06", "2026-07"],
        [grafico.Serie("receitas", [100, 200], "receitas"),
         grafico.Serie("despesas", [50, 400], "despesas")],
    )
    assert svg.count("<rect") == 4
    assert svg.startswith("<svg") and svg.endswith("</svg>")


def test_grafico_escala_pela_maior_barra():
    """A maior barra ocupa a altura útil inteira; a metade, metade dela."""
    import re

    svg = grafico.barras(["m"], [grafico.Serie("s", [50], "a"), grafico.Serie("t", [100], "b")])
    alturas = [float(h) for h in re.findall(r'height="([\d.]+)"', svg)]
    assert alturas[1] == pytest.approx(alturas[0] * 2, rel=1e-6)


def test_grafico_vazio_quando_nao_ha_o_que_desenhar():
    assert grafico.barras([], []) == ""
    assert grafico.barras(["m"], [grafico.Serie("s", [0], "a")]) == ""


def test_grafico_escapa_conteudo():
    """Descrição vem do extrato do usuário: não pode injetar markup no SVG."""
    svg = grafico.barras(["<script>"], [grafico.Serie("x", [10], "a")])
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


# ---------- camada 2: smoke de rota ----------


def test_painel_responde_html_em_banco_vazio(cliente_vazio):
    r = cliente_vazio.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    for marca in ("{{", "Undefined", "None"):
        assert marca not in r.text


def test_painel_responde_html_com_dados(cliente_semeado):
    r = cliente_semeado.get("/")
    assert r.status_code == 200
    for marca in ("{{", "Undefined", "None"):
        assert marca not in r.text


def test_css_e_servido(cliente_vazio):
    r = cliente_vazio.get("/static/painel.css")
    assert r.status_code == 200 and len(r.content) > 500


def test_dispensar_pelo_painel_muda_o_banco_e_redireciona(cliente_semeado):
    from personalos.nucleo import insights as motor
    from personalos.nucleo.modulo import Insight, RegraInsight

    engine = cliente_semeado.app.state.engine
    regra = RegraInsight("t", lambda _e: [Insight("k", "algo")])
    motor.gerar(engine, (Modulo(nome="financas", metadata=None, regras_insights=(regra,)),))  # type: ignore[arg-type]
    alvo = motor.listar(engine, status="novo")[0].id

    r = cliente_semeado.post(
        f"/painel/insights/{alvo}/dispensar", follow_redirects=False
    )
    assert r.status_code == 303  # PRG: F5 não repete o POST
    assert [i.id for i in motor.listar(engine, status="dispensado")] == [alvo]


def test_perguntar_sem_consultor_nao_da_erro_no_navegador(cliente_semeado):
    """A API devolve 501 nesse caso; o painel devolve a página com aviso, porque
    tela de erro no navegador não ajuda ninguém."""
    r = cliente_semeado.post("/painel/perguntar", data={"texto": "quanto gastei?"})
    assert r.status_code == 200
    assert "não configurado" in r.text


def test_perguntar_com_consultor_mostra_a_resposta(tmp_path):
    from personalos.nucleo.portas.chat import Pergunta, Resposta

    class ChatFalso:
        def responder(self, pergunta: Pergunta) -> Resposta:
            return Resposta(texto=f"eco {pergunta.texto}")

    cliente = cliente_navegador(criar_app(db=tmp_path / "t.db", chat=ChatFalso()))
    r = cliente.post("/painel/perguntar", data={"texto": "oi"})
    assert r.status_code == 200 and "eco oi" in r.text


# ---------- camada 3: âncoras (orçamento: 4 de 6) ----------


def test_ancoras_das_secoes_com_dados(cliente_semeado):
    html = cliente_semeado.get("/").text
    assert 'id="secao-resumo"' in html
    assert 'id="secao-graficos"' in html  # 2 meses semeados


def test_secao_de_insights_some_quando_nao_ha_insight(cliente_semeado):
    html = cliente_semeado.get("/").text
    assert 'id="secao-insights"' not in html
    assert 'id="lista-insights"' not in html


# ---------- teste de arquitetura ----------


def test_painel_nao_conhece_nenhum_modulo():
    """Mecaniza a mitigação anti-scope-creep da spec: conteúdo novo no painel só
    entra por campo do manifesto, nunca hardcoded na rota."""
    import personalos.painel as pacote

    raiz = Path(pacote.__file__).parent
    infratores = [
        arquivo.relative_to(raiz).as_posix()
        for padrao in ("*.py", "*.html", "*.css")
        for arquivo in raiz.rglob(padrao)
        if "financas" in arquivo.read_text(encoding="utf-8")
    ]
    assert infratores == [], f"painel citando módulo: {infratores}"


def test_painel_com_zero_modulos_ainda_renderiza(tmp_path):
    cliente = cliente_navegador(criar_app(db=tmp_path / "t.db", modulos=(), fluxo_mensal=lambda _e: []))
    r = cliente.get("/")
    assert r.status_code == 200
