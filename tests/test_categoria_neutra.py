"""Categorias que não são consumo, declaradas pelo usuário.

O domínio já sabia que transferência e investimento movem dinheiro sem gastá-lo,
mas a lista era fixa no código: ("Transferência", "Investimento"). Nos dados
reais a categoria que o banco usa para transferência própria se chama "Conta de
uso" — nome que o código não tinha como adivinhar. Resultado: R$ 24 mil de
dinheiro indo e voltando contavam como despesa, e o sistema recomendava cortar
justamente o que nunca saiu do bolso.
"""
from datetime import date
from pathlib import Path

import pytest

from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.aplicacao import analise, escrita
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao, e_consumo
from personalos.modulos.financas.infra.repositorios import RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo.db import criar_engine

HOJE = date(2026, 8, 20)


@pytest.fixture
def engine_com_movimentacao(tmp_path: Path):
    engine = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    RepoTransacoesSQL(engine).inserir_muitas(
        [
            *[
                Transacao(f"g{m}", date(2026, m, 10), Dinheiro(-30000), f"MERCADO {m:02d}",
                          "conta", "Alimentação")
                for m in (4, 5, 6, 7)
            ],
            *[
                Transacao(f"t{m}", date(2026, m, 11), Dinheiro(-290000), f"PIX TRANSF PARA MIM {m:02d}",
                          "conta", "Conta de uso")
                for m in (4, 5, 6, 7)
            ],
        ]
    )
    return engine


def test_categoria_do_banco_domina_o_ranking_enquanto_nao_e_declarada(engine_com_movimentacao):
    """O estado de hoje, registrado: sem declarar, 'Conta de uso' lidera o corte."""
    cortes = analise.onde_cortar(engine_com_movimentacao, limite=3, hoje=HOJE)

    assert cortes[0].descricao == "Conta de uso"


def test_declarar_nao_consumo_tira_a_categoria_do_onde_cortar(engine_com_movimentacao):
    escrita.declarar_nao_consumo(engine_com_movimentacao, "Conta de uso")

    cortes = analise.onde_cortar(engine_com_movimentacao, limite=3, hoje=HOJE)

    assert all(c.descricao != "Conta de uso" for c in cortes)
    assert cortes[0].descricao == "Alimentação"


def test_declarar_nao_consumo_reduz_o_custo_basico(engine_com_movimentacao):
    """Custo básico é 'quanto custa existir'. Mandar dinheiro para si mesmo não
    custa nada — incluir isso infla o número que orienta toda decisão."""
    antes = analise.custo_basico_mensal(engine_com_movimentacao, hoje=HOJE)
    escrita.declarar_nao_consumo(engine_com_movimentacao, "Conta de uso")
    depois = analise.custo_basico_mensal(engine_com_movimentacao, hoje=HOJE)

    assert depois.total_centavos < antes.total_centavos


def test_os_padroes_do_dominio_continuam_valendo():
    """Transferência e Investimento seguem fora do consumo sem ninguém declarar."""
    assert not e_consumo("Transferência")
    assert not e_consumo("Investimento")
    assert e_consumo("Alimentação")


def test_gasto_por_categoria_nao_conta_movimentacao(engine_com_movimentacao):
    """Duas telas discordando é pior que uma errada: o gráfico mostrava
    'Investimento' como 17% do gasto enquanto o ranking de cortes o ignorava,
    porque só o segundo respeitava e_consumo. Quem olha as duas não sabe em qual
    acreditar."""
    from personalos.modulos.financas.aplicacao import consultas
    from personalos.modulos.financas.infra.repositorios import RepoTransacoesSQL

    escrita.declarar_nao_consumo(engine_com_movimentacao, "Conta de uso")
    repo = RepoTransacoesSQL(engine_com_movimentacao)

    categorias = dict(
        (nome, valor.centavos)
        for nome, valor in consultas.gastos_por_categoria(
            repo, nao_consumo=escrita.categorias_nao_consumo(engine_com_movimentacao)
        )
    )

    assert "Conta de uso" not in categorias
    assert "Alimentação" in categorias


def test_nao_consumo_com_data_de_inicio_preserva_o_periodo_anterior(engine_com_movimentacao):
    """A transferência só é neutra a partir do mês em que a OUTRA conta passa a
    ser importada. Antes disso ela é a única pista do gasto, e neutralizá-la
    apagaria despesa real do histórico.

    Caso concreto: transferências desde agosto, extrato da conta destino a partir
    de janeiro. Neutralizar tudo sumiria com cinco meses de gasto.
    """
    escrita.declarar_nao_consumo(
        engine_com_movimentacao, "Conta de uso", a_partir_de=date(2026, 6, 1)
    )

    por_mes = {m.mes: m for m in analise._por_mes(engine_com_movimentacao, hoje=HOJE)}

    def gasto(mes: str) -> int:
        m = por_mes[mes]
        return m.fixo_centavos + m.variavel_centavos

    # Abril: a transferência ainda conta como gasto (R$ 300 + R$ 2.900)
    assert gasto("2026-04") == 320000
    # Junho em diante: só o gasto de verdade (R$ 300)
    assert gasto("2026-06") == 30000
