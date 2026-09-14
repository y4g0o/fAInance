"""Sugestão de regras de categorização — dados sintéticos, nenhum extrato real."""
from datetime import date
from pathlib import Path

from personalos.modulos.financas.analytics.vistas import VISTAS
from personalos.modulos.financas.aplicacao.sugestoes import _padrao_comum, sugerir_regras
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Regra, Transacao
from personalos.modulos.financas.infra.repositorios import RepoRegrasSQL, RepoTransacoesSQL
from personalos.modulos.financas.infra.tabelas import metadata as metadata_financas
from personalos.nucleo.db import criar_engine


def _engine(tmp_path: Path, transacoes: list[Transacao]):
    engine = criar_engine(tmp_path / "t.db", metadatas=(metadata_financas,), vistas=VISTAS)
    if transacoes:
        RepoTransacoesSQL(engine).inserir_muitas(transacoes)
    return engine


def _tx(fit: str, dia: int, centavos: int, desc: str, cat=None):
    return Transacao(fit, date(2026, 6, dia), Dinheiro(-centavos), desc, "conta", cat)


# ---------- escolha do padrão ----------


def test_padrao_comum_escolhe_a_palavra_que_identifica():
    """Entre PIX, QRS e CLARO, a que identifica o gasto é a mais longa — sem precisar
    de lista de palavras genéricas, que envelhece mal."""
    assert _padrao_comum(["PIX QRS TELECOMIX05/08", "PIX QRS TELECOMIX12/07"]) == "telecomix"
    assert _padrao_comum(["INT /TRIBUTO-UF/GUIA 202646", "INT /TRIBUTO-UF/GUIA 202702"]) == "tributo"


def test_padrao_comum_ignora_numero_e_pontuacao():
    # o que muda entre ocorrências (data, parcela, documento) não pode virar padrão
    assert _padrao_comum(["UBER TRIP 123", "UBER TRIP 456"]) == "uber"


def test_padrao_comum_desempata_de_forma_deterministica():
    """'uber' e 'trip' têm o mesmo tamanho. max() sobre set não garante ordem, então
    sem desempate explícito a sugestão mudaria entre execuções sobre os mesmos dados."""
    for _ in range(20):
        assert _padrao_comum(["UBER TRIP 1", "UBER TRIP 2"]) == "uber"


def test_padrao_comum_sem_palavra_compartilhada():
    assert _padrao_comum(["ABC 1", "XYZ 2"]) is None


# ---------- sugestões ----------


def test_agrupa_sem_categoria_e_ordena_por_dinheiro(tmp_path):
    """Ordena por total, não por contagem: uma regra que cobre três gastos grandes
    vale mais que uma que cobre trinta cafés."""
    engine = _engine(tmp_path, [
        _tx("a1", 1, 500, "CAFE DA ESQUINA 01/06"),
        _tx("a2", 2, 500, "CAFE DA ESQUINA 02/06"),
        _tx("a3", 3, 500, "CAFE DA ESQUINA 03/06"),
        _tx("b1", 4, 90000, "PIX QRS ALUGUEL05/06"),
        _tx("b2", 5, 90000, "PIX QRS ALUGUEL05/07"),
    ])
    sugestoes = sugerir_regras(engine)
    # 'esquina' e não 'cafe': a heurística é a palavra mais LONGA em comum. Nem
    # sempre é a mais natural para um humano, mas é sempre um padrão que funciona —
    # e o usuário pode editar o padrão antes de criar a regra.
    assert [s.padrao for s in sugestoes] == ["aluguel", "esquina"]
    assert sugestoes[0].total_centavos == 180000
    assert sugestoes[0].ocorrencias == 2
    assert sugestoes[1].ocorrencias == 3


def test_ignora_transacao_que_ja_tem_categoria(tmp_path):
    engine = _engine(tmp_path, [
        _tx("a1", 1, 500, "CAFE DA ESQUINA 01/06", "Alimentação"),
        _tx("a2", 2, 500, "CAFE DA ESQUINA 02/06", "Alimentação"),
        _tx("b1", 3, 9000, "FARMACIA CENTRAL 03/06"),
        _tx("b2", 4, 9000, "FARMACIA CENTRAL 04/06"),
    ])
    assert [s.padrao for s in sugerir_regras(engine)] == ["farmacia"]


def test_alcance_conta_tambem_as_ja_categorizadas(tmp_path):
    """O alcance mostra o efeito real da regra antes de criá-la: se ela pegaria mais
    linhas do que as sem categoria, é sinal de que já existe regra concorrente."""
    engine = _engine(tmp_path, [
        _tx("a1", 1, 500, "CAFE DA ESQUINA 01/06", "Alimentação"),
        _tx("a2", 2, 500, "CAFE DA ESQUINA 02/06"),
        _tx("a3", 3, 500, "CAFE DA ESQUINA 03/06"),
    ])
    sugestao = sugerir_regras(engine)[0]
    assert sugestao.ocorrencias == 2  # sem categoria
    assert sugestao.alcance == 3  # todas


def test_respeita_minimo_de_ocorrencias(tmp_path):
    engine = _engine(tmp_path, [_tx("a1", 1, 500, "GASTO UNICO 01/06")])
    assert sugerir_regras(engine) == []
    assert len(sugerir_regras(engine, minimo_de_ocorrencias=1)) == 1


def test_respeita_o_limite(tmp_path):
    transacoes = []
    for i in range(6):
        transacoes += [
            _tx(f"x{i}a", 1, 100 * (i + 1), f"LOJA{chr(65 + i)}ABC 01/06"),
            _tx(f"x{i}b", 2, 100 * (i + 1), f"LOJA{chr(65 + i)}ABC 02/06"),
        ]
    engine = _engine(tmp_path, transacoes)
    assert len(sugerir_regras(engine, limite=3)) == 3


def test_ignora_receita(tmp_path):
    engine = _engine(tmp_path, [
        Transacao("s1", date(2026, 6, 1), Dinheiro(500000), "SALARIO EMPRESA", "conta"),
        Transacao("s2", date(2026, 6, 2), Dinheiro(500000), "SALARIO EMPRESA", "conta"),
    ])
    assert sugerir_regras(engine) == []


def test_banco_vazio_nao_quebra(tmp_path):
    assert sugerir_regras(_engine(tmp_path, [])) == []


def test_regra_criada_a_partir_da_sugestao_realmente_categoriza(tmp_path):
    """Fecha o ciclo: a sugestão tem de produzir uma regra que funciona de verdade
    no categorizador — senão é conselho inútil."""
    from personalos.modulos.financas.dominio.categorizador import categorizar

    engine = _engine(tmp_path, [
        _tx("a1", 1, 9000, "PIX QRS FARMACIA05/06"),
        _tx("a2", 2, 9000, "PIX QRS FARMACIA05/07"),
    ])
    sugestao = sugerir_regras(engine)[0]
    RepoRegrasSQL(engine).adicionar(Regra(sugestao.padrao, "Saúde"))
    regras = RepoRegrasSQL(engine).listar()
    transacao = RepoTransacoesSQL(engine).listar()[0]
    assert categorizar(transacao, regras) == "Saúde"


# ---------- comando ----------


def test_comando_sugerir_regras_mostra_volume_e_como_criar(tmp_path):
    from typer.testing import CliRunner

    from personalos.modulos.financas.cli import app

    db = tmp_path / "t.db"
    engine = criar_engine(db, metadatas=(metadata_financas,), vistas=VISTAS)
    RepoTransacoesSQL(engine).inserir_muitas([
        _tx("a1", 1, 90000, "PIX QRS ALUGUEL05/06"),
        _tx("a2", 2, 90000, "PIX QRS ALUGUEL05/07"),
    ])
    saida = CliRunner().invoke(app, ["sugerir-regras", "--db", str(db)]).stdout
    assert "'aluguel'" in saida
    assert "R$ 1.800,00" in saida
    assert "financas regra" in saida  # diz como agir


def test_comando_sugerir_regras_sem_nada_a_sugerir(tmp_path):
    from typer.testing import CliRunner

    from personalos.modulos.financas.cli import app

    db = tmp_path / "vazio.db"
    criar_engine(db, metadatas=(metadata_financas,), vistas=VISTAS)
    resultado = CliRunner().invoke(app, ["sugerir-regras", "--db", str(db)])
    assert resultado.exit_code == 0
    assert "Nada a sugerir" in resultado.stdout


# ---------- recategorizar ----------


def test_recategorizar_aplica_regras_ao_que_ja_esta_no_banco(tmp_path):
    """Criar regra depois de importar não fazia nada: o INSERT OR IGNORE pula as
    linhas existentes, então reimportar NÃO recategoriza. A própria saída do
    sugerir-regras instruía o usuário a fazer algo que não funcionava."""
    from personalos.modulos.financas.aplicacao.sugestoes import recategorizar

    engine = _engine(tmp_path, [_tx("a1", 1, 9000, "PIX QRS FARMACIA05/06")])
    RepoRegrasSQL(engine).adicionar(Regra("farmacia", "Saúde"))
    assert recategorizar(engine) == 1
    assert RepoTransacoesSQL(engine).listar()[0].categoria == "Saúde"


def test_recategorizar_preserva_categoria_existente_por_padrao(tmp_path):
    """Sobrescrever categoria já atribuída destruiria correção manual do usuário."""
    from personalos.modulos.financas.aplicacao.sugestoes import recategorizar

    engine = _engine(tmp_path, [_tx("a1", 1, 9000, "PIX QRS FARMACIA05/06", "Escolhi À Mão")])
    RepoRegrasSQL(engine).adicionar(Regra("farmacia", "Saúde"))
    assert recategorizar(engine) == 0
    assert RepoTransacoesSQL(engine).listar()[0].categoria == "Escolhi À Mão"


def test_recategorizar_com_reaplicar_tudo_sobrescreve(tmp_path):
    from personalos.modulos.financas.aplicacao.sugestoes import recategorizar

    engine = _engine(tmp_path, [_tx("a1", 1, 9000, "PIX QRS FARMACIA05/06", "Antiga")])
    RepoRegrasSQL(engine).adicionar(Regra("farmacia", "Saúde"))
    assert recategorizar(engine, reaplicar_tudo=True) == 1
    assert RepoTransacoesSQL(engine).listar()[0].categoria == "Saúde"


def test_recategorizar_sem_regra_que_case_nao_muda_nada(tmp_path):
    from personalos.modulos.financas.aplicacao.sugestoes import recategorizar

    engine = _engine(tmp_path, [_tx("a1", 1, 9000, "MERCADO")])
    RepoRegrasSQL(engine).adicionar(Regra("farmacia", "Saúde"))
    assert recategorizar(engine) == 0
    assert RepoTransacoesSQL(engine).listar()[0].categoria is None
