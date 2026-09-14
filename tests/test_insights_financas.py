"""Detecção de gastos fixos e regras de insight — tudo determinístico."""
from datetime import date
from pathlib import Path

from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.modulos.financas.insights import (
    normalizar_descricao,
    aprender_gastos_fixos,
    detectar_gastos_fixos,
    regra_categoria_acima_da_media,
    regra_fixo_ausente,
    regra_fixo_aumentou,
)
from personalos.modulos.financas.modulo import MODULO
from personalos.nucleo import insights as motor
from personalos.nucleo import memoria
from personalos.nucleo.db import criar_engine

HOJE = date(2026, 8, 5)


def _engine(tmp_path: Path, transacoes: list[Transacao]):
    engine = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    if transacoes:
        RepoTransacoesSQL(engine).inserir_muitas(transacoes)
    return engine


def _despesa(fit: str, ano: int, mes: int, dia: int, centavos: int, desc: str, cat=None):
    return Transacao(fit, date(ano, mes, dia), Dinheiro(-centavos), desc, "nubank", cat)


def _netflix(meses: list[int], centavos: int = 3990, ano: int = 2026):
    return [
        _despesa(f"nf{ano}{m}", ano, m, 10, centavos, f"NETFLIX.COM {m:02d}/{ano % 100}", "Lazer")
        for m in meses
    ]


# ---------- normalização ----------


def test_normalizar_remove_data_e_parcela_do_extrato():
    assert normalizar_descricao("NETFLIX.COM 08/26") == "netflix com"
    assert normalizar_descricao("PARCELA 3/12 GELADEIRA") == "parcela geladeira"
    assert normalizar_descricao("Uber   Trip  123ABC") == "uber trip abc"


# ---------- detecção ----------


def test_detecta_gasto_fixo_com_tres_meses_de_valor_estavel(tmp_path):
    engine = _engine(tmp_path, _netflix([6, 7, 8]))
    fixos = detectar_gastos_fixos(engine, HOJE)
    assert [f.chave for f in fixos] == ["netflix com"]
    assert fixos[0].valor_mediano_centavos == 3990
    assert fixos[0].meses == ("2026-06", "2026-07", "2026-08")


def test_dois_meses_nao_bastam(tmp_path):
    engine = _engine(tmp_path, _netflix([7, 8]))
    assert detectar_gastos_fixos(engine, HOJE) == []


def test_valor_instavel_nao_e_fixo(tmp_path):
    # Mercado: recorrente, mas imprevisível — não é gasto fixo.
    engine = _engine(tmp_path, [
        _despesa("m1", 2026, 6, 3, 12000, "MERCADO BOM PRECO"),
        _despesa("m2", 2026, 7, 8, 45000, "MERCADO BOM PRECO"),
        _despesa("m3", 2026, 8, 1, 89000, "MERCADO BOM PRECO"),
    ])
    assert detectar_gastos_fixos(engine, HOJE) == []


def test_fixo_que_parou_de_acontecer_nao_conta(tmp_path):
    # Cancelado em março: mais de MESES_INATIVIDADE sem aparecer.
    engine = _engine(tmp_path, _netflix([1, 2, 3]))
    assert detectar_gastos_fixos(engine, HOJE) == []


def test_receita_recorrente_nao_e_gasto_fixo(tmp_path):
    engine = _engine(tmp_path, [
        Transacao(f"s{m}", date(2026, m, 5), Dinheiro(500000), "SALARIO", "nubank")
        for m in (6, 7, 8)
    ])
    assert detectar_gastos_fixos(engine, HOJE) == []


def test_banco_vazio_nao_quebra(tmp_path):
    assert detectar_gastos_fixos(_engine(tmp_path, []), HOJE) == []


# ---------- memória ----------


def test_aprender_grava_na_memoria_e_reaprender_nao_duplica(tmp_path):
    engine = _engine(tmp_path, _netflix([6, 7, 8]))
    aprender_gastos_fixos(engine, HOJE)
    aprender_gastos_fixos(engine, HOJE)
    fatos = memoria.listar(engine, "financas", "gasto_fixo")
    assert len(fatos) == 1
    assert fatos[0].chave == "netflix com"
    assert fatos[0].valor["valor_mediano_centavos"] == 3990


def test_esquecer_um_fixo_aprendido(tmp_path):
    engine = _engine(tmp_path, _netflix([6, 7, 8]))
    aprender_gastos_fixos(engine, HOJE)
    assert memoria.remover(engine, "financas", "gasto_fixo", "netflix com") is True
    assert memoria.listar(engine, "financas", "gasto_fixo") == []


# ---------- regras ----------


def test_regra_ausente_avisa_quando_o_fixo_falta_no_ultimo_mes(tmp_path):
    # Aprende com mai/jun/jul, depois entra uma transação em agosto de OUTRA coisa:
    # agosto passa a ser o último mês com dados e a Netflix não aparece nele.
    # O dia 20 é depois do dia habitual da Netflix (10), então a ausência já venceu —
    # antes disso o alerta seria ruído (ver test_fixo_nao_e_cobrado_antes_do_dia_habitual).
    engine = _engine(tmp_path, _netflix([5, 6, 7]))
    aprender_gastos_fixos(engine, date(2026, 7, 20))
    RepoTransacoesSQL(engine).inserir_muitas([_despesa("x1", 2026, 8, 20, 5000, "PADARIA")])
    encontrados = regra_fixo_ausente(engine)
    assert len(encontrados) == 1
    assert "não apareceu em 2026-08" in encontrados[0].titulo
    assert encontrados[0].chave_dedup == "netflix com:2026-08"


def test_regra_ausente_silenciosa_quando_o_fixo_apareceu(tmp_path):
    engine = _engine(tmp_path, _netflix([6, 7, 8]))
    aprender_gastos_fixos(engine, HOJE)
    assert regra_fixo_ausente(engine) == []


def test_regra_aumento_detecta_reajuste(tmp_path):
    engine = _engine(tmp_path, _netflix([5, 6, 7]) + _netflix([8], centavos=5990))
    aprender_gastos_fixos(engine, HOJE)
    encontrados = regra_fixo_aumentou(engine)
    assert len(encontrados) == 1
    assert "subiu" in encontrados[0].titulo
    assert encontrados[0].detalhe["valor_atual_centavos"] == 5990
    assert encontrados[0].severidade == "alerta"  # +50% é alerta, não só atenção


def test_regra_aumento_ignora_variacao_pequena(tmp_path):
    engine = _engine(tmp_path, _netflix([5, 6, 7]) + _netflix([8], centavos=4100))
    aprender_gastos_fixos(engine, HOJE)
    assert regra_fixo_aumentou(engine) == []


def test_regra_categoria_acima_da_media(tmp_path):
    # Alimentação estável em 3 meses e explodindo no quarto.
    transacoes = [
        _despesa(f"a{m}", 2026, m, 10, 40000, f"MERCADO {m}", "Alimentação")
        for m in (5, 6, 7)
    ] + [_despesa("a8", 2026, 8, 3, 120000, "MERCADO 8", "Alimentação")]
    engine = _engine(tmp_path, transacoes)
    encontrados = regra_categoria_acima_da_media(engine)
    assert len(encontrados) == 1
    assert encontrados[0].detalhe["categoria"] == "Alimentação"
    assert encontrados[0].detalhe["total_centavos"] == 120000
    assert encontrados[0].chave_dedup == "Alimentação:2026-08"


def test_regra_categoria_precisa_de_base_de_comparacao(tmp_path):
    engine = _engine(tmp_path, [_despesa("a1", 2026, 8, 3, 120000, "MERCADO", "Alimentação")])
    assert regra_categoria_acima_da_media(engine) == []


# ---------- motor ----------


def test_motor_grava_e_deduplica(tmp_path):
    engine = _engine(tmp_path, _netflix([5, 6, 7]) + _netflix([8], centavos=5990))
    aprender_gastos_fixos(engine, HOJE)
    primeiro = motor.gerar(engine, (MODULO,))
    assert primeiro.novos >= 1
    assert primeiro.falhas == ()
    segundo = motor.gerar(engine, (MODULO,))
    assert segundo.novos == 0
    assert segundo.ja_existiam == primeiro.novos


def test_insight_dispensado_nao_reaparece(tmp_path):
    engine = _engine(tmp_path, _netflix([5, 6, 7]) + _netflix([8], centavos=5990))
    aprender_gastos_fixos(engine, HOJE)
    motor.gerar(engine, (MODULO,))
    alvo = motor.listar(engine, status="novo")[0]
    assert motor.definir_status(engine, alvo.id, "dispensado") is True
    motor.gerar(engine, (MODULO,))
    assert [i.id for i in motor.listar(engine, status="novo")] != [alvo.id]
    assert [i.id for i in motor.listar(engine, status="dispensado")] == [alvo.id]


def test_regra_que_explode_nao_derruba_as_outras(tmp_path):
    from personalos.nucleo.modulo import Modulo, RegraInsight

    def explode(_engine):
        raise RuntimeError("boom")

    engine = _engine(tmp_path, _netflix([5, 6, 7]) + _netflix([8], centavos=5990))
    aprender_gastos_fixos(engine, HOJE)
    modulo = Modulo(
        nome="financas",
        metadata=metadata_financas,
        regras_insights=(RegraInsight("explode", explode), *MODULO.regras_insights),
    )
    resultado = motor.gerar(engine, (modulo,))
    assert resultado.falhas == ("explode",)
    assert resultado.novos >= 1  # as regras boas rodaram


def test_status_invalido_e_recusado(tmp_path):
    import pytest

    engine = _engine(tmp_path, [])
    with pytest.raises(ValueError, match="status inválido"):
        motor.definir_status(engine, 1, "arquivado")


def test_fixo_cancelado_para_de_avisar_em_vez_de_incomodar_pra_sempre(tmp_path):
    # Netflix em jan/fev/mar e cancelada. A padaria mantém movimento nos meses
    # seguintes. Como a chave de dedup inclui o mês, sem um corte de inatividade
    # cada mês novo geraria um alerta novo — para sempre.
    engine = _engine(tmp_path, _netflix([1, 2, 3]))
    aprender_gastos_fixos(engine, date(2026, 3, 20))
    repo = RepoTransacoesSQL(engine)
    avisos_por_mes = {}
    for mes in (4, 5, 6, 7, 8):
        # dia 20: depois do dia habitual da Netflix (10), senão o corte de
        # "ainda não venceu" mascararia o que este teste quer medir.
        repo.inserir_muitas([_despesa(f"p{mes}", 2026, mes, 20, 1500, "PADARIA")])
        aprender_gastos_fixos(engine, date(2026, mes, 20))
        avisos_por_mes[mes] = len(regra_fixo_ausente(engine))
    # Avisa enquanto a ausência é recente (abril, maio) e depois cala.
    assert avisos_por_mes == {4: 1, 5: 1, 6: 0, 7: 0, 8: 0}


def test_fixo_nao_e_cobrado_antes_do_dia_habitual_no_mes_em_curso(tmp_path):
    """Mês corrente incompleto não pode gerar 'não apareceu'.

    Bug encontrado com dados reais: os extratos terminavam no dia 5 de agosto, e a
    regra acusou ausência de 4 dos 6 gastos fixos — todos com dia habitual depois do
    dia 5. Alertar que o aluguel do dia 10 'não apareceu' no dia 5 é ruído, e ruído
    treina o usuário a ignorar a lista inteira.
    """
    # Netflix sempre no dia 10; dados terminam no dia 5 de agosto.
    engine = _engine(tmp_path, _netflix([5, 6, 7]))
    RepoTransacoesSQL(engine).inserir_muitas([_despesa("p1", 2026, 8, 5, 1500, "PADARIA")])
    aprender_gastos_fixos(engine, date(2026, 8, 5))
    assert regra_fixo_ausente(engine) == []


def test_fixo_e_cobrado_quando_o_dia_habitual_ja_passou(tmp_path):
    """Passado o dia habitual e sem lançamento, o alerta é legítimo."""
    engine = _engine(tmp_path, _netflix([5, 6, 7]))
    RepoTransacoesSQL(engine).inserir_muitas([_despesa("p1", 2026, 8, 20, 1500, "PADARIA")])
    aprender_gastos_fixos(engine, date(2026, 8, 20))
    encontrados = regra_fixo_ausente(engine)
    assert len(encontrados) == 1
    assert "não apareceu em 2026-08" in encontrados[0].titulo


def test_dia_tipico_e_a_mediana_dos_dias_de_ocorrencia(tmp_path):
    engine = _engine(tmp_path, _netflix([5, 6, 7]))  # sempre dia 10
    fixos = aprender_gastos_fixos(engine, HOJE)
    assert fixos[0].dia_tipico == 10


def test_descricao_exemplo_perde_a_data_colada_no_fim():
    """Os extratos reais truncam a descrição e colam a data: 'PIX QRS TELECOMIX05/08'.
    Isso aparece no painel, nos insights e no custo básico — limpar na exibição é
    diferente de normalizar para identidade (que já remove todo dígito)."""
    from personalos.modulos.financas.insights import limpar_descricao

    assert limpar_descricao("PIX QRS TELECOMIX05/08") == "PIX QRS TELECOMIX"
    assert limpar_descricao("PIX TRANSF Fulano05/08") == "PIX TRANSF Fulano"
    assert limpar_descricao("INT /TRIBUTO-UF/GUIA 202646") == "INT /TRIBUTO-UF/GUIA 202646"
    assert limpar_descricao("NETFLIX.COM 08/26") == "NETFLIX.COM"
    assert limpar_descricao("MERCADO") == "MERCADO"


def test_fixo_aprendido_guarda_descricao_limpa(tmp_path):
    engine = _engine(tmp_path, _netflix([6, 7, 8]))
    fixos = aprender_gastos_fixos(engine, HOJE)
    assert fixos[0].descricao_exemplo == "NETFLIX.COM"
