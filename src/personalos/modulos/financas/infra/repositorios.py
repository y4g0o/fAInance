"""Repositórios SQLAlchemy (implementam os ports). Mapeiam linha<->dataclass."""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from personalos.modulos.financas.dominio.dinheiro import Dinheiro
from personalos.modulos.financas.dominio.modelos import Regra, Transacao
from personalos.modulos.financas.infra.tabelas import contas as t_contas
from personalos.modulos.financas.infra.tabelas import regras as t_regras
from personalos.modulos.financas.infra.tabelas import transacoes as t_tx


class RepoTransacoesSQL:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def inserir_muitas(self, transacoes: list[Transacao]) -> int:
        if not transacoes:
            return 0
        linhas = [
            {
                "fit_id": t.fit_id,
                "data": t.data,
                "valor_centavos": t.valor.centavos,
                "descricao": t.descricao,
                "conta": t.conta,
                "categoria": t.categoria,
            }
            for t in transacoes
        ]
        # INSERT OR IGNORE por fit_id (dedup idempotente)
        stmt = sqlite_insert(t_tx).on_conflict_do_nothing(index_elements=["fit_id"])
        with self._engine.begin() as conn:
            existentes = {r[0] for r in conn.execute(select(t_tx.c.fit_id))}
            conn.execute(stmt, linhas)
            vistos: set[str] = set()
            novos = 0
            for t in transacoes:
                if t.fit_id not in existentes and t.fit_id not in vistos:
                    novos += 1
                vistos.add(t.fit_id)
            return novos

    def definir_categoria(self, fit_ids: list[str], categoria: str | None) -> int:
        """Define a categoria das transações dadas. Devolve quantas mudaram.

        Só a categoria: valor, data e descrição vêm do banco e são fonte da
        verdade — editá-los faria a reimportação brigar com a edição do usuário.

        O retorno é a contagem REAL de linhas afetadas, e não o tamanho da lista:
        é com ele que a interface desfaz exatamente o que mudou.
        """
        if not fit_ids:
            return 0
        with self._engine.begin() as conn:
            resultado = conn.execute(
                update(t_tx).where(t_tx.c.fit_id.in_(fit_ids)).values(categoria=categoria)
            )
            return int(resultado.rowcount)

    def listar(
        self, inicio: date | None = None, fim: date | None = None
    ) -> list[Transacao]:
        stmt = select(t_tx).order_by(t_tx.c.data, t_tx.c.fit_id)
        if inicio is not None:
            stmt = stmt.where(t_tx.c.data >= inicio)
        if fim is not None:
            stmt = stmt.where(t_tx.c.data <= fim)
        with self._engine.connect() as conn:
            return [
                Transacao(
                    fit_id=row["fit_id"],
                    data=row["data"],
                    valor=Dinheiro(row["valor_centavos"]),
                    descricao=row["descricao"],
                    conta=row["conta"],
                    categoria=row["categoria"],
                )
                for row in conn.execute(stmt).mappings()
            ]


class RepoRegrasSQL:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def listar(self) -> list[Regra]:
        with self._engine.connect() as conn:
            return [
                Regra(
                    padrao=row["padrao"],
                    categoria=row["categoria"],
                    tipo=row["tipo"],
                    prioridade=row["prioridade"],
                )
                for row in conn.execute(select(t_regras)).mappings()
            ]

    def remover(self, padrao: str, tipo: str = "contem") -> int:
        """Remove uma regra. Devolve quantas saíram — usado pelo desfazer do lote."""
        with self._engine.begin() as conn:
            resultado = conn.execute(
                delete(t_regras).where(t_regras.c.padrao == padrao, t_regras.c.tipo == tipo)
            )
            return int(resultado.rowcount)

    def adicionar(self, regra: Regra) -> bool:
        stmt = sqlite_insert(t_regras).on_conflict_do_nothing(
            index_elements=["padrao", "tipo"]
        )
        with self._engine.begin() as conn:
            resultado = conn.execute(
                stmt,
                {
                    "padrao": regra.padrao,
                    "categoria": regra.categoria,
                    "tipo": regra.tipo,
                    "prioridade": regra.prioridade,
                },
            )
            return resultado.rowcount > 0


class RepoContasSQL:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def definir_saldo_inicial(self, nome: str, saldo_inicial: Dinheiro) -> None:
        if not nome.strip():
            raise ValueError("nome da conta não pode ser vazio")
        stmt = (
            sqlite_insert(t_contas)
            .values(nome=nome, saldo_inicial_centavos=saldo_inicial.centavos)
            .on_conflict_do_update(
                index_elements=["nome"],
                set_={"saldo_inicial_centavos": saldo_inicial.centavos},
            )
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def listar(self) -> list[tuple[str, Dinheiro]]:
        with self._engine.connect() as conn:
            return [
                (row["nome"], Dinheiro(row["saldo_inicial_centavos"]))
                for row in conn.execute(select(t_contas)).mappings()
            ]
