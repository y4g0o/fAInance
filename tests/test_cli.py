from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.cli import app
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Transacao
from personalos.modulos.financas.infra.repositorios import RepoContasSQL, RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo.db import criar_engine

runner = CliRunner()


def _db(tmp_path: Path) -> Path:
    return tmp_path / "financas.db"


def test_regra_adiciona_com_sucesso(tmp_path):
    resultado = runner.invoke(app, ["regra", "uber", "Transporte", "--db", str(_db(tmp_path))])
    assert resultado.exit_code == 0
    assert "Regra adicionada" in resultado.stdout


def test_regra_duplicada_nao_sobrescreve(tmp_path):
    db = _db(tmp_path)
    runner.invoke(app, ["regra", "uber", "Transporte", "--db", str(db)])
    resultado = runner.invoke(app, ["regra", "uber", "TransporteX", "--db", str(db)])
    assert resultado.exit_code == 0
    assert "já existe" in resultado.stdout
    assert "adicionada" not in resultado.stdout


def test_regra_tipo_invalido_nao_gera_traceback(tmp_path):
    resultado = runner.invoke(
        app, ["regra", "x", "y", "--tipo", "invalido", "--db", str(_db(tmp_path))]
    )
    assert resultado.exit_code == 1
    assert "Erro:" in resultado.stdout
    assert "tipo inválido" in resultado.stdout
    assert not isinstance(resultado.exception, ValueError)


def test_gastos_filtra_por_ano_isolado(tmp_path):
    db = _db(tmp_path)
    engine = criar_engine(db, metadatas=(metadata_financas,))
    repo = RepoTransacoesSQL(engine)
    repo.inserir_muitas(
        [
            Transacao("a", date(2020, 3, 1), Dinheiro(-1000), "compra antiga", "nubank"),
            Transacao("b", date(2026, 3, 1), Dinheiro(-2000), "compra recente", "nubank"),
        ]
    )
    resultado = runner.invoke(app, ["gastos", "--ano", "2020", "--db", str(db)])
    assert resultado.exit_code == 0
    assert "compra antiga" in resultado.stdout
    assert "compra recente" not in resultado.stdout


def test_importar_pasta_inexistente(tmp_path):
    resultado = runner.invoke(
        app, ["importar", str(tmp_path / "nao-existe"), "--db", str(_db(tmp_path))]
    )
    assert resultado.exit_code == 1
    assert "Pasta não encontrada" in resultado.stdout


def test_conta_define_saldo_inicial(tmp_path):
    resultado = runner.invoke(app, ["conta", "nubank", "500,00", "--db", str(_db(tmp_path))])
    assert resultado.exit_code == 0
    assert "saldo inicial definido" in resultado.stdout
    assert "R$ 500,00" in resultado.stdout


def test_conta_nome_vazio_gera_erro_claro(tmp_path):
    resultado = runner.invoke(app, ["conta", "", "100,00", "--db", str(_db(tmp_path))])
    assert resultado.exit_code == 1
    assert "Erro:" in resultado.stdout
    assert not isinstance(resultado.exception, ValueError)


def test_conta_saldo_invalido_nao_gera_traceback(tmp_path):
    resultado = runner.invoke(app, ["conta", "nubank", "abacate", "--db", str(_db(tmp_path))])
    assert resultado.exit_code == 1
    assert "Erro:" in resultado.stdout
    assert not isinstance(resultado.exception, ValueError)


def test_saldo_inclui_saldo_inicial_da_conta(tmp_path):
    db = _db(tmp_path)
    engine = criar_engine(db, metadatas=(metadata_financas,), vistas=VISTAS)
    RepoTransacoesSQL(engine).inserir_muitas(
        [Transacao("a", date(2026, 6, 1), Dinheiro(10000), "salario", "nubank")]
    )
    RepoContasSQL(engine).definir_saldo_inicial("nubank", Dinheiro(50000))
    resultado = runner.invoke(app, ["saldo", "--db", str(db)])
    assert resultado.exit_code == 0
    assert "R$ 600,00" in resultado.stdout


def test_fluxo_mostra_entradas_e_saidas(tmp_path):
    db = _db(tmp_path)
    engine = criar_engine(db, metadatas=(metadata_financas,), vistas=VISTAS)
    RepoTransacoesSQL(engine).inserir_muitas(
        [
            Transacao("a", date(2026, 6, 1), Dinheiro(300000), "salario", "nubank"),
            Transacao("b", date(2026, 6, 2), Dinheiro(-99900), "mercado", "nubank"),
        ]
    )
    resultado = runner.invoke(app, ["fluxo", "--db", str(db)])
    assert resultado.exit_code == 0
    assert "2026-06" in resultado.stdout
    assert "R$ 3.000,00" in resultado.stdout
    assert "R$ 999,00" in resultado.stdout
    assert "R$ 2.001,00" in resultado.stdout


def test_lancar_despesa_grava_com_sinal_negativo(tmp_path):
    db = _db(tmp_path)
    resultado = runner.invoke(
        app, ["lancar", "mercado", "50,00", "--data", "2026-08-01", "--db", str(db)]
    )
    assert resultado.exit_code == 0
    assert "-R$ 50,00" in resultado.stdout
    engine = criar_engine(db, metadatas=(metadata_financas,), vistas=VISTAS)
    transacoes = RepoTransacoesSQL(engine).listar()
    assert len(transacoes) == 1
    assert transacoes[0].valor.centavos == -5000
    assert transacoes[0].conta == "manual"


def test_lancar_receita_grava_com_sinal_positivo(tmp_path):
    db = _db(tmp_path)
    resultado = runner.invoke(
        app, ["lancar", "freela", "1.200,00", "--tipo", "receita", "--db", str(db)]
    )
    assert resultado.exit_code == 0
    engine = criar_engine(db, metadatas=(metadata_financas,), vistas=VISTAS)
    assert RepoTransacoesSQL(engine).listar()[0].valor.centavos == 120000


def test_lancar_aplica_regra_de_categorizacao_existente(tmp_path):
    db = _db(tmp_path)
    runner.invoke(app, ["regra", "uber", "Transporte", "--db", str(db)])
    resultado = runner.invoke(app, ["lancar", "uber para o centro", "23,50", "--db", str(db)])
    assert "[Transporte]" in resultado.stdout


def test_lancar_categoria_explicita_vence_a_regra(tmp_path):
    db = _db(tmp_path)
    runner.invoke(app, ["regra", "uber", "Transporte", "--db", str(db)])
    resultado = runner.invoke(
        app, ["lancar", "uber", "23,50", "--categoria", "Trabalho", "--db", str(db)]
    )
    assert "[Trabalho]" in resultado.stdout


def test_lancar_identico_no_mesmo_dia_nao_duplica(tmp_path):
    db = _db(tmp_path)
    args = ["lancar", "cafe", "7,00", "--data", "2026-08-01", "--db", str(db)]
    assert runner.invoke(app, args).exit_code == 0
    segundo = runner.invoke(app, args)
    assert segundo.exit_code == 0
    assert "Já existe um lançamento idêntico" in segundo.stdout
    engine = criar_engine(db, metadatas=(metadata_financas,), vistas=VISTAS)
    assert len(RepoTransacoesSQL(engine).listar()) == 1


def test_lancar_valor_zero_e_recusado(tmp_path):
    resultado = runner.invoke(app, ["lancar", "x", "0", "--db", str(_db(tmp_path))])
    assert resultado.exit_code == 1
    assert "valor deve ser positivo" in resultado.stdout


def test_lancar_valor_negativo_e_recusado(tmp_path):
    # "-50" só chega como argumento depois de "--" (antes disso o Click o lê como opção).
    resultado = runner.invoke(app, ["lancar", "--db", str(_db(tmp_path)), "--", "x", "-50"])
    assert resultado.exit_code == 1
    assert "valor deve ser positivo" in resultado.stdout


def test_lancar_tipo_invalido_e_recusado(tmp_path):
    resultado = runner.invoke(
        app, ["lancar", "x", "50", "--tipo", "transferencia", "--db", str(_db(tmp_path))]
    )
    assert resultado.exit_code == 1
    assert "tipo inválido" in resultado.stdout


def test_lancar_data_invalida_e_recusada(tmp_path):
    resultado = runner.invoke(
        app, ["lancar", "x", "50", "--data", "01/08/2026", "--db", str(_db(tmp_path))]
    )
    assert resultado.exit_code == 1
    assert "Erro" in resultado.stdout


def test_lancar_entra_no_saldo(tmp_path):
    db = _db(tmp_path)
    runner.invoke(app, ["lancar", "salario", "3.000,00", "--tipo", "receita", "--db", str(db)])
    runner.invoke(app, ["lancar", "mercado", "200,00", "--db", str(db)])
    resultado = runner.invoke(app, ["saldo", "--db", str(db)])
    assert "R$ 2.800,00" in resultado.stdout


def test_esquecer_fixo_de_chave_nova_registra_e_nao_falha(tmp_path):
    """Marcar de antemão algo que você sabe que será detectado errado é uso
    legítimo. Sair com erro escondia que a decisão tinha sido guardada."""
    db = tmp_path / "t.db"
    resultado = CliRunner().invoke(
        app, ["esquecer-fixo", "assinatura qualquer", "--db", str(db)]
    )

    assert resultado.exit_code == 0
    assert "não ser aprendido" in resultado.stdout


def test_renomear_categoria_junta_variantes_pela_cli(tmp_path):
    """'compras' e 'Compras' viram duas fatias do mesmo gasto no relatório."""
    db = tmp_path / "t.db"
    engine = criar_engine(db, metadatas=(metadata_financas,), vistas=VISTAS)
    RepoTransacoesSQL(engine).inserir_muitas(
        [
            Transacao("a1", date(2026, 6, 1), Dinheiro(-1000), "LOJA UM", "c", "compras"),
            Transacao("a2", date(2026, 6, 2), Dinheiro(-2000), "LOJA DOIS", "c", "Compras"),
        ]
    )

    resultado = CliRunner().invoke(
        app, ["renomear-categoria", "compras", "Compras", "--db", str(db)]
    )

    assert resultado.exit_code == 0
    assert "1 transação" in resultado.stdout
    categorias = {t.categoria for t in RepoTransacoesSQL(engine).listar()}
    assert categorias == {"Compras"}
