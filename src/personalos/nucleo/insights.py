"""Motor de insights — itera as regras dos módulos e grava o que for novo.

Dedup por (regra_id, chave_dedup): rodar duas vezes não repete o alerta, e um
insight dispensado não volta (o status fica na linha que já existe). Regra que
explode não derruba as outras — o motor conta a falha e segue.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import case, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from personalos.nucleo.modulo import Modulo
from personalos.nucleo.tabelas import insights as t_insights

STATUS_VALIDOS = ("novo", "visto", "dispensado")


@dataclass(frozen=True)
class InsightGravado:
    id: int
    modulo: str
    regra_id: str
    chave_dedup: str
    titulo: str
    detalhe: dict[str, object]
    severidade: str
    status: str
    criado_em: str


@dataclass(frozen=True)
class Resultado:
    novos: int
    ja_existiam: int
    falhas: tuple[str, ...]  # ids das regras que levantaram exceção


def gerar(engine: Engine, modulos: Sequence[Modulo]) -> Resultado:
    agora = datetime.now(timezone.utc).isoformat()
    novos = ja_existiam = 0
    falhas: list[str] = []
    for modulo in modulos:
        for regra in modulo.regras_insights:
            try:
                produzidos = regra.avaliar(engine)
            except Exception:  # noqa: BLE001 — uma regra ruim não invalida as outras
                falhas.append(regra.id)
                continue
            for insight in produzidos:
                stmt = (
                    sqlite_insert(t_insights)
                    .values(
                        modulo=modulo.nome,
                        regra_id=regra.id,
                        chave_dedup=insight.chave_dedup,
                        titulo=insight.titulo,
                        detalhe=json.dumps(insight.detalhe),
                        severidade=insight.severidade,
                        status="novo",
                        criado_em=agora,
                    )
                    .on_conflict_do_nothing(index_elements=["regra_id", "chave_dedup"])
                )
                with engine.begin() as conn:
                    if conn.execute(stmt).rowcount:
                        novos += 1
                    else:
                        ja_existiam += 1
    return Resultado(novos, ja_existiam, tuple(falhas))


def listar(
    engine: Engine, status: str | None = "novo", modulo: str | None = None
) -> list[InsightGravado]:
    # Ordem explícita por gravidade: depender da ordem alfabética de
    # alerta/atencao/info funcionaria hoje e quebraria no primeiro rename.
    prioridade = case({"alerta": 0, "atencao": 1, "info": 2}, value=t_insights.c.severidade, else_=3)
    consulta = select(t_insights).order_by(
        prioridade, t_insights.c.criado_em.desc(), t_insights.c.id
    )
    if status is not None:
        consulta = consulta.where(t_insights.c.status == status)
    if modulo is not None:
        consulta = consulta.where(t_insights.c.modulo == modulo)
    with engine.connect() as conn:
        return [
            InsightGravado(
                r.id, r.modulo, r.regra_id, r.chave_dedup, r.titulo,
                json.loads(r.detalhe), r.severidade, r.status, r.criado_em,
            )
            for r in conn.execute(consulta)
        ]


def definir_status(engine: Engine, insight_id: int, status: str) -> bool:
    """Marca visto/dispensado. False se o id não existe."""
    if status not in STATUS_VALIDOS:
        raise ValueError(f"status inválido: {status!r} (use {'|'.join(STATUS_VALIDOS)})")
    with engine.begin() as conn:
        resultado = conn.execute(
            update(t_insights).where(t_insights.c.id == insight_id).values(status=status)
        )
    return resultado.rowcount > 0
