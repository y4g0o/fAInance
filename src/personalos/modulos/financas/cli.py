"""CLI do módulo financas (Typer). Toda lógica vem dos casos de uso."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import cast

import typer
from sqlalchemy import text
from sqlalchemy.engine import Engine

from personalos.modulos.financas.analytics.vistas import VISTAS as _vistas_financas
from personalos.modulos.financas.aplicacao import analise, consultas, escrita, sugestoes
from personalos.modulos.financas.aplicacao.importar import importar_extratos
from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas import insights as insights_financas
from personalos.modulos.financas.infra.leitores import detectar_leitor
from personalos.modulos.financas.infra.leitores import pdf as leitor_pdf
from personalos.modulos.financas.infra.repositorios import (
    RepoContasSQL,
    RepoRegrasSQL,
    RepoTransacoesSQL,
)
from personalos.modulos.financas.infra.tabelas import metadata as _metadata_financas
from personalos.nucleo import memoria
from personalos.nucleo.config import caminho_banco
from personalos.nucleo.db import criar_engine

app = typer.Typer(help="Módulo financeiro do PersonalOS.")

EXTRATOS_PADRAO = Path(__file__).resolve().parents[4] / "extratos"


def _repos(db: Path) -> tuple[RepoTransacoesSQL, RepoRegrasSQL]:
    engine = criar_engine(db, metadatas=(_metadata_financas,), vistas=_vistas_financas)
    return RepoTransacoesSQL(engine), RepoRegrasSQL(engine)


def _engine_financas(db: Path | None) -> Engine:
    """Engine com o schema e as views do módulo (as do kernel vêm sempre)."""
    return criar_engine(
        db or caminho_banco(), metadatas=(_metadata_financas,), vistas=_vistas_financas
    )


def _periodo(mes: int | None, ano: int | None) -> tuple[date | None, date | None]:
    if mes is None and ano is None:
        return None, None
    ano_resolvido = ano or date.today().year
    if mes is None:
        return date(ano_resolvido, 1, 1), date(ano_resolvido, 12, 31)
    fim_mes = date(ano_resolvido + (mes // 12), (mes % 12) + 1, 1)
    return date(ano_resolvido, mes, 1), fim_mes - timedelta(days=1)


@app.command()
def importar(
    pasta: Path = typer.Argument(EXTRATOS_PADRAO),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Importa todos os CSV/OFX/QFX/XLSX/PDF de uma pasta."""
    db_resolvido = db or caminho_banco()
    if not pasta.is_dir():
        typer.echo(f"Pasta não encontrada: {pasta}")
        raise typer.Exit(1)
    repo_tx, repo_regras = _repos(db_resolvido)
    arquivos = [
        str(p) for p in sorted(pasta.iterdir())
        if p.suffix.lower() in (".csv", ".ofx", ".qfx", ".xlsx", ".pdf")
    ]
    if not arquivos:
        typer.echo(f"Nenhum extrato em {pasta}")
        raise typer.Exit()
    try:
        novas = importar_extratos(arquivos, repo_tx, repo_regras, detectar_leitor)
    except ValueError as e:
        typer.echo(f"Erro ao importar: {e}")
        raise typer.Exit(1) from e
    typer.echo(f"{novas} transações novas importadas de {len(arquivos)} arquivo(s).")

    # Importar é o "evento" desta fatia: reaprende os gastos fixos e roda as regras
    # (sem EventBus — o gatilho documentado para criá-lo é o 2º par publicador/assinante).
    if novas:
        # Import local: modulo.py importa este cli.py, então importar o manifesto no
        engine = criar_engine(
            db_resolvido, metadatas=(_metadata_financas,), vistas=_vistas_financas
        )
        novos = escrita.reprocessar_insights(engine)
        if novos:
            typer.echo(f"{novos} insight(s) novo(s) — veja com `personalos insights listar`.")


@app.command()
def saldo(db: Path | None = typer.Option(None, "--db")) -> None:
    """Saldo total (entradas - saídas + saldo inicial das contas declaradas)."""
    db_resolvido = db or caminho_banco()
    engine = criar_engine(db_resolvido, metadatas=(_metadata_financas,), vistas=_vistas_financas)
    with engine.connect() as conn:
        centavos = conn.execute(
            text("SELECT saldo_centavos FROM vw_financas_saldo_v1")
        ).scalar_one()
    typer.echo(f"Saldo: {Dinheiro(centavos).formatar()}")


@app.command()
def gastos(
    mes: int | None = typer.Option(None, "--mes", help="1-12", min=1, max=12),
    ano: int | None = typer.Option(None, "--ano"),
    limite: int = typer.Option(10, "--limite"),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Maiores gastos do período."""
    db_resolvido = db or caminho_banco()
    repo_tx, _ = _repos(db_resolvido)
    inicio, fim = _periodo(mes, ano)
    for t in consultas.maiores_gastos(repo_tx, limite, inicio, fim):
        typer.echo(f"{t.data}  {t.valor.formatar():>14}  {t.descricao}")


@app.command()
def categorias(
    mes: int | None = typer.Option(None, "--mes", min=1, max=12),
    ano: int | None = typer.Option(None, "--ano"),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Total gasto por categoria."""
    db_resolvido = db or caminho_banco()
    repo_tx, _ = _repos(db_resolvido)
    inicio, fim = _periodo(mes, ano)
    nao_consumo = escrita.categorias_nao_consumo(_engine_financas(db))
    for nome, total in consultas.gastos_por_categoria(repo_tx, inicio, fim, nao_consumo):
        typer.echo(f"{total.formatar():>14}  {nome}")


@app.command()
def fluxo(db: Path | None = typer.Option(None, "--db")) -> None:
    """Fluxo mensal: receitas, despesas e resultado por mês."""
    db_resolvido = db or caminho_banco()
    engine = criar_engine(db_resolvido, metadatas=(_metadata_financas,), vistas=_vistas_financas)
    for linha in consultas.fluxo_mensal(engine):
        receitas = Dinheiro(cast(int, linha["receitas_centavos"])).formatar()
        despesas = Dinheiro(cast(int, linha["despesas_centavos"])).formatar()
        resultado = Dinheiro(cast(int, linha["resultado_centavos"])).formatar()
        typer.echo(f"{linha['mes']}  Receitas: {receitas}  Despesas: {despesas}  Resultado: {resultado}")


@app.command("sugerir-regras")
def sugerir_regras_cmd(
    limite: int = typer.Option(10, "--limite", min=1, max=50),
    minimo: int = typer.Option(2, "--minimo", min=1, help="ocorrências mínimas no grupo"),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Onde está o dinheiro sem categoria, e a regra que cobriria cada grupo.

    Depois de importar um ano de extrato tudo nasce sem categoria, e criar regra de
    uma em uma é inviável. Aqui os gastos são agrupados pela mesma normalização que a
    detecção de gasto fixo usa, e ordenados pelo VALOR que representam — meia dúzia
    de regras costuma cobrir a maior parte do dinheiro.

    A categoria é escolha sua: a ferramenta só mostra onde está o volume. A coluna
    'alc' é o alcance — quantas transações o padrão pegaria no total, inclusive as já
    categorizadas; se for maior que 'ocor', já existe regra concorrente.
    """
    engine = _engine_financas(db)
    encontradas = sugestoes.sugerir_regras(engine, limite, minimo)
    if not encontradas:
        typer.echo("Nada a sugerir: ou tudo está categorizado, ou não há grupo repetido.")
        raise typer.Exit()
    typer.echo(f"{'total':>14}  {'ocor':>4} {'alc':>4}  padrao / exemplo")
    for s in encontradas:
        typer.echo(
            f"{Dinheiro(s.total_centavos).formatar():>14}  {s.ocorrencias:>4} "
            f"{s.alcance:>4}  {s.padrao!r} - {s.exemplo}"
        )
    typer.echo(
        "\nPara criar uma regra:  personalos financas regra <padrao> <Categoria>"
        "\nDepois de criar as regras:  personalos financas recategorizar"
        "\n(reimportar NÃO recategoriza: o dedup por fit_id pula o que já existe)"
    )


@app.command()
def recategorizar(
    reaplicar_tudo: bool = typer.Option(
        False, "--reaplicar-tudo", help="também sobrescreve categoria já atribuída"
    ),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Aplica as regras atuais às transações já gravadas.

    Por padrão só preenche o que está sem categoria — sobrescrever o que você
    ajustou à mão seria destruir trabalho seu.
    """
    mudadas = sugestoes.recategorizar(_engine_financas(db), reaplicar_tudo)
    typer.echo(f"{mudadas} transação(ões) recategorizada(s).")


@app.command("inspecionar-pdf")
def inspecionar_pdf(
    arquivo: Path,
    amostras: int = typer.Option(8, "--amostras", min=1, max=30),
) -> None:
    """Radiografa a estrutura de um extrato em PDF, SEM revelar o conteúdo.

    Toda linha de exemplo sai mascarada: letra vira 'a', dígito vira '9', pontuação e
    posição preservadas. Serve para calibrar o leitor de um banco novo — a saída pode
    ser colada num chat sem expor estabelecimento, valor ou nome. O que ela revela é
    formato de data, formato de valor, ordem das colunas e onde o total aparece; e a
    quantidade de dígitos, ou seja a ordem de grandeza dos valores.
    """
    if not arquivo.is_file():
        typer.echo(f"Arquivo não encontrado: {arquivo}")
        raise typer.Exit(1)
    try:
        d = leitor_pdf.diagnosticar(str(arquivo), amostras)
    except Exception as e:  # noqa: BLE001 — PDF corrompido/protegido não deve dar traceback
        typer.echo(f"Não foi possível ler o PDF: {type(e).__name__}")
        raise typer.Exit(1) from e

    typer.echo(f"páginas: {d.paginas}   linhas de texto: {d.linhas}")
    typer.echo(f"com data: {d.com_data}   com valor: {d.com_valor}   candidatas: {d.candidatas}")
    if not d.candidatas:
        typer.echo(
            "\nNenhuma linha com data E valor. Provavelmente é PDF escaneado (imagem, "
            "sem camada de texto) — precisaria de OCR."
        )
        raise typer.Exit()
    typer.echo("\nAmostras de transação (mascaradas) e quantos valores há em cada linha:")
    for mascarada, quantos in zip(d.amostras_mascaradas, d.valores_por_candidata):
        typer.echo(f"  [{quantos} valor(es)] {mascarada}")
    if d.amostras_de_total:
        typer.echo("\nLinhas de saldo/total (mascaradas) — usadas na reconciliação:")
        for mascarada in d.amostras_de_total:
            typer.echo(f"  {mascarada}")
    else:
        typer.echo("\nNenhuma linha de saldo/total encontrada: reconciliação ficará indisponível.")


@app.command("custo-basico")
def custo_basico(db: Path | None = typer.Option(None, "--db")) -> None:
    """Quanto custa existir por mês: gastos fixos + mediana do variável."""
    engine = _engine_financas(db)
    b = analise.custo_basico_mensal(engine)
    if b.meses_considerados == 0:
        typer.echo("Sem meses fechados o suficiente — importe mais extratos.")
        raise typer.Exit()
    typer.echo(f"Custo básico mensal: {Dinheiro(b.total_centavos).formatar()}")
    typer.echo(f"  fixos            {Dinheiro(b.fixos_centavos).formatar():>14}")
    typer.echo(f"  variável (med.)  {Dinheiro(b.variavel_centavos).formatar():>14}")
    typer.echo(f"  base: {b.meses_considerados} mês(es) fechado(s)")
    for descricao, valor in b.fixos:
        typer.echo(f"    {Dinheiro(valor).formatar():>14}  {descricao}")


@app.command("onde-cortar")
def onde_cortar_cmd(
    limite: int = typer.Option(5, "--limite"),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Candidatos a corte ranqueados pelo impacto ANUAL."""
    cortes = analise.onde_cortar(_engine_financas(db), limite)
    if not cortes:
        typer.echo("Sem histórico suficiente para ranquear cortes.")
        raise typer.Exit()
    for c in cortes:
        typer.echo(
            f"{Dinheiro(c.anual_centavos).formatar():>14}/ano  "
            f"({Dinheiro(c.mensal_centavos).formatar()}/mês)  {c.descricao}  [{c.tipo}]"
        )


@app.command("pode-comprar")
def pode_comprar_cmd(
    valor: str,
    parcelas: int = typer.Option(1, "--parcelas"),
    parcela: str | None = typer.Option(None, "--parcela", help="valor da parcela que a loja informou"),
    taxa: float = typer.Option(0.0, "--taxa", help="juro mensal, ex: 0.02 para 2%/mês"),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Os números de uma compra — sem veredito, a decisão é sua."""
    try:
        total = Dinheiro.de_texto(valor)
        parcela_centavos = Dinheiro.de_texto(parcela).centavos if parcela else None
        c = analise.pode_comprar(
            _engine_financas(db), total.centavos, parcelas, taxa, parcela_centavos
        )
    except ValueError as e:
        typer.echo(f"Erro: {e}")
        raise typer.Exit(1) from e

    typer.echo(f"{Dinheiro(c.valor_centavos).formatar()} em {c.parcelas}x de "
               f"{Dinheiro(c.parcela_centavos).formatar()}")
    if c.juros_centavos:
        taxa_txt = f"{c.taxa_mensal:.2%}/mês" if c.taxa_mensal is not None else "indeterminada"
        typer.echo(f"  custo total    {Dinheiro(c.custo_total_centavos).formatar():>14}  "
                   f"(juros {Dinheiro(c.juros_centavos).formatar()}, taxa {taxa_txt})")
    else:
        typer.echo("  sem juros embutidos")
    typer.echo(f"  custo básico   {Dinheiro(c.custo_basico_centavos).formatar():>14}/mês")
    typer.echo(f"  folga mensal   {Dinheiro(c.folga_mensal_centavos).formatar():>14}")
    if c.percentual_da_folga is not None:
        typer.echo(f"  a parcela consome {c.percentual_da_folga:.0%} da folga")
    else:
        typer.echo("  ATENÇÃO: sem folga mensal (custo básico >= receita mediana)")
    if c.meses_de_reserva is not None:
        typer.echo(f"  reserva atual cobre {c.meses_de_reserva:.1f} mês(es) de custo básico")


@app.command()
def projecao(db: Path | None = typer.Option(None, "--db")) -> None:
    """Como o mês corrente deve fechar, pelo ritmo de gasto + fixos pendentes."""
    p = analise.projecao_fim_do_mes(_engine_financas(db))
    if p is None:
        typer.echo("Nenhum movimento no mês corrente — nada a projetar.")
        raise typer.Exit()
    typer.echo(f"{p.mes} (dia {p.dias_corridos} de {p.dias_no_mes})")
    typer.echo(f"  gasto até agora  {Dinheiro(p.gasto_ate_agora_centavos).formatar():>14}")
    typer.echo(f"  fixos pendentes  {Dinheiro(p.fixos_pendentes_centavos).formatar():>14}")
    typer.echo(f"  projeção do mês  {Dinheiro(p.projecao_centavos).formatar():>14}")
    typer.echo(f"  receita prevista {Dinheiro(p.receita_prevista_centavos).formatar():>14}")
    resultado = p.receita_prevista_centavos - p.projecao_centavos
    typer.echo(f"  resultado        {Dinheiro(resultado).formatar():>14}")


@app.command()
def fixos(
    aprender: bool = typer.Option(
        True, "--aprender/--so-listar", help="detecta e atualiza a memória antes de listar"
    ),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Gastos fixos aprendidos do histórico (assinaturas, aluguel, contas)."""
    db_resolvido = db or caminho_banco()
    engine = criar_engine(db_resolvido, metadatas=(_metadata_financas,), vistas=_vistas_financas)
    if aprender:
        insights_financas.aprender_gastos_fixos(engine)
    fatos = memoria.listar(engine, insights_financas.MODULO, insights_financas.TIPO_FATO)
    if not fatos:
        typer.echo(
            "Nenhum gasto fixo detectado ainda — são necessários "
            f"{insights_financas.MESES_MINIMOS} meses com o mesmo gasto."
        )
        return
    for fato in sorted(fatos, key=lambda f: -int(cast(int, f.valor["valor_mediano_centavos"]))):
        valor = Dinheiro(cast(int, fato.valor["valor_mediano_centavos"]))
        meses = cast(list, fato.valor["meses"])
        typer.echo(
            f"{valor.formatar():>14}  {fato.valor['descricao_exemplo']}  "
            f"({len(meses)} meses, última em {fato.valor['ultima_data']})"
        )


@app.command("renomear-categoria")
def renomear_categoria_cmd(
    de: str,
    para: str,
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Junta variantes de categoria: 'compras' e 'Compras' viram uma só.

    A comparação é exata: o sistema não presume que maiúscula e minúscula são a
    mesma palavra — em nome próprio nem sempre são. Quem decide é você.
    """
    db_resolvido = db or caminho_banco()
    repo_tx, _ = _repos(db_resolvido)
    try:
        mudadas = escrita.renomear_categoria(repo_tx, de=de, para=para)
    except ValueError as e:
        typer.echo(f"Erro: {e}")
        raise typer.Exit(1) from e
    typer.echo(f"{mudadas} transação(ões) movida(s) de '{de}' para '{para}'.")


@app.command("esquecer-fixo")
def esquecer_fixo(
    chave: str,
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Esquece um gasto fixo detectado errado (use a chave normalizada de `fixos`)."""
    db_resolvido = db or caminho_banco()
    engine = criar_engine(db_resolvido, metadatas=(_metadata_financas,), vistas=_vistas_financas)
    # Mesmo quando a chave ainda não foi aprendida, o "não é fixo" é registrado:
    # serve para marcar de antemão algo que você sabe que vai ser detectado errado.
    # Dizer "não existia" e sair com erro esconderia que a decisão foi guardada.
    if insights_financas.esquecer_fixo(engine, chave):
        typer.echo(f"Esquecido: {chave} (não volta a ser aprendido)")
    else:
        typer.echo(f"{chave!r} não estava na lista, mas fica marcado para não ser aprendido.")


@app.command()
def lancar(
    descricao: str,
    valor: str,
    tipo: str = typer.Option("despesa", "--tipo", help="despesa|receita"),
    data_iso: str | None = typer.Option(None, "--data", help="YYYY-MM-DD (padrão: hoje)"),
    conta: str = typer.Option("manual", "--conta"),
    categoria: str | None = typer.Option(None, "--categoria"),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Lança uma transação manual (dinheiro vivo, PIX, o que não vem em extrato).

    O valor é sempre MAGNITUDE (positivo); quem decide o sinal é --tipo. Sem
    --categoria, aplica as regras de categorização já cadastradas.

    ATENÇÃO: use --conta apenas para contas que você NÃO importa por extrato —
    lançar aqui algo que depois vem no OFX conta duas vezes. O padrão 'manual'
    mantém esses lançamentos visivelmente separados das contas importadas.
    """
    db_resolvido = db or caminho_banco()
    repo_tx, repo_regras = _repos(db_resolvido)
    try:
        quando = date.fromisoformat(data_iso) if data_iso else date.today()
        resultado = escrita.lancar(
            repo_tx,
            repo_regras,
            RepoContasSQL(_engine_financas(db)),
            descricao=descricao,
            valor=valor,
            tipo=tipo,
            quando=quando,
            conta=conta,
            categoria=categoria,
        )
    except ValueError as e:
        typer.echo(f"Erro: {e}")
        raise typer.Exit(1) from e

    transacao = resultado.transacao
    if not resultado.inserida:
        typer.echo(
            f"Já existe um lançamento idêntico em {transacao.data} "
            f"({transacao.valor.formatar()}, '{descricao}') — nada inserido."
        )
        raise typer.Exit()
    rotulo = transacao.categoria or "sem categoria"
    typer.echo(f"Lançado: {transacao.data}  {transacao.valor.formatar()}  {descricao}  [{rotulo}]")


@app.command()
def regra(
    padrao: str,
    categoria: str,
    tipo: str = typer.Option("contem", "--tipo", help="contem|regex"),
    prioridade: int = typer.Option(100, "--prioridade"),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Adiciona uma regra de categorização."""
    db_resolvido = db or caminho_banco()
    _, repo_regras = _repos(db_resolvido)
    try:
        criada = escrita.adicionar_regra(
            repo_regras, padrao=padrao, categoria=categoria, tipo=tipo, prioridade=prioridade
        )
    except ValueError as e:
        typer.echo(f"Erro: {e}")
        raise typer.Exit(1) from e
    if criada:
        typer.echo(f"Regra adicionada: '{padrao}' → {categoria}")
    else:
        typer.echo(f"Regra já existe para padrão '{padrao}' (tipo {tipo}) — não alterada.")


@app.command()
def conta(
    nome: str,
    saldo_inicial: str,
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Define o saldo inicial de uma conta (usado pro cálculo correto do saldo total)."""
    db_resolvido = db or caminho_banco()
    engine = criar_engine(db_resolvido, metadatas=(_metadata_financas,), vistas=_vistas_financas)
    repo_contas = RepoContasSQL(engine)
    try:
        valor = escrita.definir_saldo_conta(repo_contas, nome=nome, saldo_inicial=saldo_inicial)
    except ValueError as e:
        typer.echo(f"Erro: {e}")
        raise typer.Exit(1) from e
    typer.echo(f"Conta '{nome}': saldo inicial definido em {valor.formatar()}")


if __name__ == "__main__":
    app()
