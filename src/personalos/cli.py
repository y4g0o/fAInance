"""CLI raiz do PersonalOS — agrega os módulos registrados."""
from __future__ import annotations

from pathlib import Path

import typer
from sqlalchemy.engine import Engine

from personalos.nucleo import insights as motor_insights
from personalos.nucleo import memoria as motor_memoria
from personalos.nucleo.backup import fazer_backup
from personalos.nucleo.config import caminho_banco, diretorio_dados
from personalos.nucleo.db import criar_engine
from personalos.composicao import MODULOS

app = typer.Typer(help="PersonalOS — plataforma pessoal local.")
insights_app = typer.Typer(help="Alertas determinísticos gerados pelos módulos.")
memoria_app = typer.Typer(help="Fatos que o PersonalOS aprendeu ou que você declarou.")
app.add_typer(insights_app, name="insights")
app.add_typer(memoria_app, name="memoria")

for _modulo in MODULOS:
    if _modulo.cli is not None:
        app.add_typer(_modulo.cli, name=_modulo.nome)


def _engine(db: Path | None) -> Engine:
    """Engine com o schema e as views de TODOS os módulos registrados."""
    return criar_engine(
        db or caminho_banco(),
        metadatas=tuple(m.metadata for m in MODULOS),
        vistas=tuple(v for m in MODULOS for v in m.vistas),
    )


SEVERIDADE_ICONE = {"alerta": "🔴", "atencao": "🟡", "info": "🔵"}


@insights_app.command("gerar")
def insights_gerar(db: Path | None = typer.Option(None, "--db")) -> None:
    """Roda as regras de todos os módulos e grava o que for novo."""
    resultado = motor_insights.gerar(_engine(db), MODULOS)
    typer.echo(f"{resultado.novos} insight(s) novo(s); {resultado.ja_existiam} já existia(m).")
    if resultado.falhas:
        typer.echo(f"Regras que falharam: {', '.join(resultado.falhas)}")


@insights_app.command("listar")
def insights_listar(
    status: str = typer.Option("novo", "--status", help="novo|visto|dispensado|todos"),
    modulo: str | None = typer.Option(None, "--modulo"),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Lista os insights (por padrão só os novos)."""
    encontrados = motor_insights.listar(
        _engine(db), status=None if status == "todos" else status, modulo=modulo
    )
    if not encontrados:
        typer.echo("Nenhum insight.")
        return
    for i in encontrados:
        icone = SEVERIDADE_ICONE.get(i.severidade, "•")
        typer.echo(f"[{i.id}] {icone} {i.titulo}")


@insights_app.command("dispensar")
def insights_dispensar(
    insight_id: int,
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Dispensa um insight — ele não volta a aparecer, mesmo gerando de novo."""
    if motor_insights.definir_status(_engine(db), insight_id, "dispensado"):
        typer.echo(f"Insight {insight_id} dispensado.")
    else:
        typer.echo(f"Insight {insight_id} não encontrado.")
        raise typer.Exit(1)


@memoria_app.command("listar")
def memoria_listar(
    modulo: str | None = typer.Option(None, "--modulo"),
    tipo: str | None = typer.Option(None, "--tipo"),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Lista os fatos guardados."""
    fatos = motor_memoria.listar(_engine(db), modulo=modulo, tipo=tipo)
    if not fatos:
        typer.echo("Memória vazia.")
        return
    for f in fatos:
        typer.echo(f"{f.modulo}/{f.tipo}/{f.chave}: {f.valor}")


@memoria_app.command("esquecer")
def memoria_esquecer(
    modulo: str,
    tipo: str,
    chave: str,
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Esquece um fato (ex: um gasto fixo detectado errado)."""
    if motor_memoria.remover(_engine(db), modulo, tipo, chave):
        typer.echo(f"Esquecido: {modulo}/{tipo}/{chave}")
    else:
        typer.echo(f"Não existia: {modulo}/{tipo}/{chave}")
        raise typer.Exit(1)


HOSTS_PERMITIDOS = ("127.0.0.1", "::1", "localhost")


def _validar_host(host: str) -> None:
    """Recusa qualquer bind que não seja loopback, sem escape hatch.

    O PersonalOS não tem autenticação: é um sistema de um usuário na própria
    máquina. Uma flag de "eu sei o que estou fazendo" seria o caminho mais curto
    para publicar a vida financeira inteira na rede local sem perceber, então ela
    não existe. Quem realmente precisar expor põe um proxy com autenticação na
    frente — decisão consciente, fora deste programa.
    """
    if host not in HOSTS_PERMITIDOS:
        raise typer.BadParameter(
            f"host {host!r} recusado: o PersonalOS não tem autenticação, e expor "
            f"fora de loopback publicaria seus dados financeiros na rede. "
            f"Permitidos: {', '.join(HOSTS_PERMITIDOS)}."
        )


@app.command()
def servir(
    host: str = typer.Option("127.0.0.1", "--host"),
    porta: int = typer.Option(8000, "--porta", min=1024, max=65535),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Sobe a API e o painel em http://127.0.0.1:8000 (só loopback)."""
    _validar_host(host)
    # Imports tardios: uvicorn e FastAPI custam centenas de ms, e a CLI é chamada
    # para tudo. Nenhum outro comando deve pagar por este.
    import uvicorn

    from personalos.api.app import criar_app

    typer.echo(f"PersonalOS em http://{host}:{porta}  (Ctrl+C para parar)")
    # Passa o objeto, não uma import string: é o que faz --db funcionar. Consequência
    # aceita e documentada: --reload não é suportado.
    uvicorn.run(criar_app(db), host=host, port=porta, log_level="warning")


@app.command()
def backup(
    destino: Path | None = typer.Option(None, "--destino"),
    db: Path | None = typer.Option(None, "--db"),
) -> None:
    """Cria um backup do banco do PersonalOS."""
    db_resolvido = db or caminho_banco()
    destino_resolvido = destino or (diretorio_dados() / "backups")
    caminho = fazer_backup(db_resolvido, destino_resolvido)
    typer.echo(f"Backup criado em {caminho}")


if __name__ == "__main__":
    app()
