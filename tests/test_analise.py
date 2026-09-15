"""Ferramentas de decisão — custo básico, cortes, compra parcelada, projeção."""
from datetime import date
from pathlib import Path

import pytest

from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.aplicacao.analise import (
    custo_basico_mensal,
    onde_cortar,
    pode_comprar,
    projecao_fim_do_mes,
)
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoContasSQL, RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.modulos.financas.insights import aprender_gastos_fixos, detectar_gastos_fixos
from personalos.nucleo.db import criar_engine

HOJE = date(2026, 8, 15)


MERCADO_POR_MES = {4: 20000, 5: 30000, 6: 60000, 7: 80000}  # mediana = 45000


def _cenario(tmp_path: Path):
    """4 meses fechados (abr–jul) + agosto em curso.

    Fixos: aluguel 1200, academia 89,90. Variável: mercado, de propósito
    IRREGULAR (200/300/600/800) — um mercado de valor idêntico todo mês seria
    classificado como gasto fixo, e aí o balde variável ficaria vazio.
    Receita: 5000/mês.
    """
    engine = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    # Saldo só existe para conta com ponto de partida declarado; sem isto,
    # "meses de reserva" não teria resposta — e não ter resposta é o correto.
    RepoContasSQL(engine).definir_saldo_inicial("nu", Dinheiro(0))
    transacoes = []
    for mes in (4, 5, 6, 7):
        transacoes += [
            Transacao(f"al{mes}", date(2026, mes, 5), Dinheiro(-120000), f"ALUGUEL {mes}/26", "nu"),
            Transacao(f"ac{mes}", date(2026, mes, 15), Dinheiro(-8990), "SMARTFIT", "nu"),
            Transacao(f"me{mes}", date(2026, mes, 20), Dinheiro(-MERCADO_POR_MES[mes]),
                      f"MERCADO {mes}", "nu", "Alimentação"),
            Transacao(f"sa{mes}", date(2026, mes, 1), Dinheiro(500000), "SALARIO", "nu"),
        ]
    # Agosto em curso: só o aluguel e um mercado pequeno até o dia 15.
    transacoes += [
        Transacao("al8", date(2026, 8, 5), Dinheiro(-120000), "ALUGUEL 08/26", "nu"),
        Transacao("me8", date(2026, 8, 10), Dinheiro(-25000), "MERCADO 8", "nu", "Alimentação"),
        Transacao("sa8", date(2026, 8, 1), Dinheiro(500000), "SALARIO", "nu"),
    ]
    RepoTransacoesSQL(engine).inserir_muitas(transacoes)
    aprender_gastos_fixos(engine, HOJE)
    return engine


# ---------- custo básico ----------


def test_custo_basico_soma_fixos_e_mediana_do_variavel(tmp_path):
    basico = custo_basico_mensal(_cenario(tmp_path), HOJE)
    assert basico.fixos_centavos == 120000 + 8990
    assert basico.variavel_centavos == 45000       # mediana dos 4 meses fechados
    assert basico.total_centavos == 173990
    assert basico.meses_considerados == 4          # agosto (em curso) ficou fora
    # descrição exibida perde a data colada no fim (limpar_descricao)
    assert [d for d, _ in basico.fixos] == ["ALUGUEL", "SMARTFIT"]


def test_custo_basico_ignora_o_mes_em_curso(tmp_path):
    # Agosto tem variável de só 250,00 até o dia 15 — abaixo de todos os meses
    # fechados. Se entrasse na mediana, o custo básico apareceria menor do que é.
    basico = custo_basico_mensal(_cenario(tmp_path), HOJE)
    assert basico.variavel_centavos == 45000


def test_custo_basico_de_banco_vazio_e_zero(tmp_path):
    engine = criar_engine(tmp_path / "v.db", metadatas=(metadata_financas,), vistas=VISTAS)
    basico = custo_basico_mensal(engine, HOJE)
    assert basico.total_centavos == 0
    assert basico.fixos == ()


# ---------- onde cortar ----------


def test_onde_cortar_ranqueia_por_impacto_anual(tmp_path):
    cortes = onde_cortar(_cenario(tmp_path), limite=5, hoje=HOJE)
    assert [c.descricao for c in cortes[:3]] == ["ALUGUEL", "Alimentação", "SMARTFIT"]
    assert cortes[0].anual_centavos == 120000 * 12
    assert cortes[0].tipo == "fixo"


def test_onde_cortar_nao_conta_o_fixo_duas_vezes(tmp_path):
    # Aluguel e academia são fixos: não podem reaparecer como categoria.
    cortes = onde_cortar(_cenario(tmp_path), limite=10, hoje=HOJE)
    categorias = [c.descricao for c in cortes if c.tipo == "categoria"]
    assert categorias == ["Alimentação"]  # 'Sem categoria' era só fixo


def test_onde_cortar_respeita_o_limite(tmp_path):
    assert len(onde_cortar(_cenario(tmp_path), limite=2, hoje=HOJE)) == 2


# ---------- vale a pena comprar ----------


def test_pode_comprar_a_vista(tmp_path):
    compra = pode_comprar(_cenario(tmp_path), 450000, parcelas=1, hoje=HOJE)
    assert compra.parcela_centavos == 450000
    assert compra.juros_centavos == 0
    # folga = receita mediana (5000) − custo básico (1789,90)
    assert compra.folga_mensal_centavos == 500000 - 173990


def test_pode_comprar_descobre_juro_embutido_no_parcelado(tmp_path):
    # A loja diz "10x de R$ 500" num produto de R$ 4.500: não é sem juros.
    compra = pode_comprar(_cenario(tmp_path), 450000, parcelas=10, parcela_centavos=50000,
                          hoje=HOJE)
    assert compra.custo_total_centavos == 500000
    assert compra.juros_centavos == 50000
    assert compra.taxa_mensal is not None
    assert 0.019 < compra.taxa_mensal < 0.020        # ~1,96%/mês
    assert compra.percentual_da_folga == pytest.approx(50000 / (500000 - 173990), rel=1e-3)


def test_pode_comprar_sem_juros_de_verdade_tem_taxa_zero(tmp_path):
    compra = pode_comprar(_cenario(tmp_path), 450000, parcelas=10, parcela_centavos=45000,
                          hoje=HOJE)
    assert compra.juros_centavos == 0
    assert compra.taxa_mensal == pytest.approx(0.0, abs=1e-9)


def test_pode_comprar_calcula_parcela_a_partir_da_taxa(tmp_path):
    compra = pode_comprar(_cenario(tmp_path), 450000, parcelas=10, taxa_mensal=0.02, hoje=HOJE)
    assert compra.parcela_centavos == pytest.approx(50097, abs=2)  # npf.pmt
    assert compra.juros_centavos > 0


def test_pode_comprar_informa_meses_de_reserva(tmp_path):
    compra = pode_comprar(_cenario(tmp_path), 100000, hoje=HOJE)
    assert compra.meses_de_reserva is not None
    assert compra.meses_de_reserva > 0
    assert compra.custo_basico_centavos == 173990


def test_pode_comprar_recusa_entrada_invalida(tmp_path):
    engine = _cenario(tmp_path)
    with pytest.raises(ValueError, match="valor deve ser positivo"):
        pode_comprar(engine, 0, hoje=HOJE)
    with pytest.raises(ValueError, match="parcelas"):
        pode_comprar(engine, 1000, parcelas=0, hoje=HOJE)


# ---------- projeção ----------


def test_projecao_soma_ritmo_variavel_e_fixos_pendentes(tmp_path):
    p = projecao_fim_do_mes(_cenario(tmp_path), HOJE)
    assert p is not None
    assert p.mes == "2026-08"
    assert p.dias_corridos == 15 and p.dias_no_mes == 31
    assert p.gasto_ate_agora_centavos == 120000 + 25000
    assert p.fixos_pendentes_centavos == 8990        # academia ainda não caiu
    # aluguel já pago (120000) + ritmo do variável (25000/15*31) + academia pendente
    assert p.projecao_centavos == 120000 + int(25000 / 15 * 31) + 8990


def test_projecao_nao_inventa_numero_sem_movimento(tmp_path):
    engine = _cenario(tmp_path)
    assert projecao_fim_do_mes(engine, date(2026, 12, 10)) is None


def test_projecao_nao_acelera_gasto_fixo_com_os_dias(tmp_path):
    # O aluguel de 1200 caiu no dia 5. Se o projetor tratasse tudo como ritmo
    # diário, projetaria ~1200/5*31 = 7440 só de aluguel.
    p = projecao_fim_do_mes(_cenario(tmp_path), HOJE)
    assert p is not None
    assert p.projecao_centavos < 300000


# ---------- não-consumo: transferência própria e aplicação não são gasto ----------


def _cenario_com_nao_consumo(tmp_path: Path):
    """4 meses fechados com salário, aluguel (fixo), mercado (variável) e — o ponto
    do teste — transferência para si mesmo e aplicação, que NÃO são consumo."""
    engine = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    # Saldo só existe para conta com ponto de partida declarado; sem isto,
    # "meses de reserva" não teria resposta — e não ter resposta é o correto.
    RepoContasSQL(engine).definir_saldo_inicial("nu", Dinheiro(0))
    transacoes = []
    for mes in (4, 5, 6, 7):
        transacoes += [
            Transacao(f"sa{mes}", date(2026, mes, 1), Dinheiro(500000), "SALARIO", "nu"),
            Transacao(f"al{mes}", date(2026, mes, 5), Dinheiro(-120000), f"ALUGUEL {mes}", "nu"),
            Transacao(f"me{mes}", date(2026, mes, 20), Dinheiro(-MERCADO_POR_MES[mes]),
                      f"MERCADO {mes}", "nu", "Alimentação"),
            Transacao(f"tr{mes}", date(2026, mes, 25), Dinheiro(-200000),
                      f"PIX TRANSF EU MESMO {mes}", "nu", "Transferência"),
            Transacao(f"ap{mes}", date(2026, mes, 26), Dinheiro(-100000),
                      f"APLICACAO CDB {mes}", "nu", "Investimento"),
        ]
    RepoTransacoesSQL(engine).inserir_muitas(transacoes)
    aprender_gastos_fixos(engine, HOJE)
    return engine


def test_custo_basico_ignora_transferencia_e_aplicacao(tmp_path):
    """Guardar dinheiro não é custo de vida. Contar isso como gasto infla o custo
    básico e faz o sistema recomendar 'corte suas aplicações'."""
    basico = custo_basico_mensal(_cenario_com_nao_consumo(tmp_path), HOJE)
    assert basico.variavel_centavos == 45000  # só o mercado, sem os 3.000 de não-consumo
    assert basico.total_centavos == 120000 + 45000


def test_onde_cortar_nao_sugere_cortar_aplicacao(tmp_path):
    cortes = onde_cortar(_cenario_com_nao_consumo(tmp_path), limite=10, hoje=HOJE)
    rotulos = [c.descricao for c in cortes]
    assert "Transferência" not in rotulos
    assert "Investimento" not in rotulos
    assert "Alimentação" in rotulos


def test_transferencia_recorrente_nao_vira_gasto_fixo(tmp_path):
    """Uma transferência mensal de valor estável tem toda a cara de gasto fixo — e
    seria o maior deles. Precisa ser excluída pela natureza, não pelo valor."""
    engine = _cenario_com_nao_consumo(tmp_path)
    fixos = detectar_gastos_fixos(engine, HOJE)
    assert all("TRANSF" not in f.descricao_exemplo.upper() for f in fixos)
    assert all("APLICACAO" not in f.descricao_exemplo.upper() for f in fixos)


def test_projecao_ignora_nao_consumo(tmp_path):
    engine = _cenario_com_nao_consumo(tmp_path)
    RepoTransacoesSQL(engine).inserir_muitas([
        Transacao("x1", date(2026, 8, 3), Dinheiro(-25000), "MERCADO 8", "nu", "Alimentação"),
        Transacao("x2", date(2026, 8, 4), Dinheiro(-500000), "PIX TRANSF EU MESMO 8", "nu",
                  "Transferência"),
    ])
    p = projecao_fim_do_mes(engine, HOJE)
    assert p is not None
    assert p.gasto_ate_agora_centavos == 25000  # a transferência de 5.000 não entra
