"""Card do financas — a mesma função que a API e o painel consomem."""
from datetime import date
from pathlib import Path

from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.aplicacao.resumo import resumo
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoContasSQL, RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo.db import criar_engine


def _engine(tmp_path: Path, transacoes=(), conta_declarada: str | None = "conta"):
    engine = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    # Saldo só conta conta com ponto de partida declarado (ver vistas.py).
    if conta_declarada:
        RepoContasSQL(engine).definir_saldo_inicial(conta_declarada, Dinheiro(0))
    if transacoes:
        RepoTransacoesSQL(engine).inserir_muitas(list(transacoes))
    return engine


def test_banco_vazio_avisa_em_vez_de_mostrar_zero(tmp_path):
    """Mostrar 'R$ 0,00' num banco vazio é inventar número. O card diz o que fazer."""
    card = resumo(_engine(tmp_path))
    assert card.vazio is True
    assert card.metricas == ()
    assert card.aviso is not None and "importar" in card.aviso


def test_com_dados_traz_tres_metricas_formatadas(tmp_path):
    engine = _engine(tmp_path, [
        Transacao("a", date(2026, 6, 1), Dinheiro(500000), "SALARIO", "conta"),
        Transacao("b", date(2026, 6, 5), Dinheiro(-120000), "ALUGUEL", "conta"),
    ])
    card = resumo(engine)
    assert card.vazio is False
    assert card.modulo == "financas"
    assert [m.rotulo for m in card.metricas] == ["Saldo", "Custo básico mensal", "Gastos fixos"]
    assert card.metricas[0].valor == "R$ 3.800,00"
    assert card.metricas[0].centavos == 380000


def test_saldo_negativo_marca_tom_de_alerta(tmp_path):
    engine = _engine(tmp_path, [
        Transacao("a", date(2026, 6, 5), Dinheiro(-120000), "ALUGUEL", "conta"),
    ])
    assert resumo(engine).metricas[0].tom == "alerta"


def test_sem_mes_fechado_nao_inventa_custo_basico(tmp_path):
    """Uma transação no mês corrente não dá base para mediana nenhuma."""
    engine = _engine(tmp_path, [
        Transacao("a", date.today(), Dinheiro(-5000), "CAFE", "conta"),
    ])
    custo = next(m for m in resumo(engine).metricas if m.rotulo == "Custo básico mensal")
    assert custo.valor == "—"
    assert custo.centavos is None


def test_card_do_manifesto_e_a_mesma_funcao():
    """Sem isso, painel e API divergem: seriam dois caminhos para o mesmo número."""
    from personalos.modulos.financas.modulo import MODULO

    assert MODULO.card is resumo
