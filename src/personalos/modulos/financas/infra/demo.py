"""Extrato SINTÉTICO para a demonstração (`personalos financas demo`).

Gera um CSV no formato genérico (date,description,amount) que passa pelo
importador real — a demo exercita o mesmo caminho de um extrato de verdade.
Nenhum valor, nome ou estabelecimento aqui é real.

O que o extrato contém, de propósito:
- gastos fixos detectáveis (≥3 meses, valor estável): aluguel, internet, streaming, academia;
- recorrentes de valor variável, que NÃO devem virar fixo (mercado, farmácia);
- grupos sem categoria, para a tela de categorizar em lote (padaria, transporte, restaurante);
- uma anomalia: uma conta de hospital no mês corrente estoura a categoria Saúde.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from personalos.modulos.financas.dominio.modelos import Regra

MESES = 6  # o mês corrente e os 5 anteriores
CONTA_DEMO = "conta"  # rótulo que o leitor CSV genérico dá às transações
SALDO_INICIAL_CENTAVOS = 250_000

REGRAS_DEMO: tuple[Regra, ...] = (
    Regra("salario", "Salário"),
    Regra("aluguel", "Moradia"),
    Regra("internet", "Contas"),
    Regra("energia", "Contas"),
    Regra("streaming", "Assinaturas"),
    Regra("academia", "Saúde"),
    Regra("farmacia", "Saúde"),
    Regra("hospital", "Saúde"),
    Regra("supermercado", "Mercado"),
)

# (dia, descrição, valor) que se repetem todo mês, com o mesmo valor.
_FIXOS = (
    (5, "SALARIO EMPRESA FICTICIA", "6200.00"),
    (7, "ACADEMIA CORPO SAO", "-89.90"),
    (10, "ALUGUEL", "-1650.00"),
    (15, "INTERNET FIBRA", "-99.90"),
    (20, "STREAMING FILMES", "-39.90"),
)

# Por mês (índice 0 = mais antigo): valores espalhados de propósito.
_ENERGIA = ("-171.40", "-188.20", "-163.90", "-195.30", "-179.60", "-184.10")
_FARMACIA = ("-48.30", "-132.90", "-71.50", "-155.20", "-39.90", "-96.40")
_MERCADO = (
    ("-412.30", "-151.20", "-268.40"),
    ("-187.45", "-358.90", "-98.70"),
    ("-296.80", "-233.10", "-445.60"),
    ("-120.35", "-389.00", "-205.75"),
    ("-331.20", "-142.80", "-478.15"),
    ("-264.90", "-110.40", "-352.30"),
)
_PADARIA = ("-6.50", "-18.90", "-11.20", "-24.00", "-9.80")
_TRANSPORTE = ("-14.90", "-32.50", "-21.70", "-47.30")
_RESTAURANTE = ("-38.00", "-94.50", "-61.20")


def _inicio_do_mes(hoje: date, meses_atras: int) -> date:
    total = hoje.year * 12 + (hoje.month - 1) - meses_atras
    return date(total // 12, total % 12 + 1, 1)


def linhas_demo(hoje: date) -> list[tuple[date, str, str]]:
    """(data, descrição, valor) dos últimos MESES meses, nada depois de `hoje`."""
    linhas: list[tuple[date, str, str]] = []
    for i in range(MESES):
        inicio = _inicio_do_mes(hoje, MESES - 1 - i)

        def dia(d: int) -> date:
            return inicio.replace(day=d)

        for d, descricao, valor in _FIXOS:
            linhas.append((dia(d), descricao, valor))
        linhas.append((dia(12), "ENERGIA ELETRICA", _ENERGIA[i]))
        linhas.append((dia(18), "FARMACIA SAUDE MAIS", _FARMACIA[i]))
        for d, valor in zip((3, 13, 24), _MERCADO[i]):
            linhas.append((dia(d), "SUPERMERCADO BOM PRECO", valor))
        for j, d in enumerate((2, 9, 16, 23)):
            linhas.append((dia(d), "PADARIA PAO QUENTE", _PADARIA[(i + j) % len(_PADARIA)]))
        for j, d in enumerate((6, 14, 21)):
            valor = _TRANSPORTE[(i + j) % len(_TRANSPORTE)]
            linhas.append((dia(d), "APP TRANSPORTE VIAGEM", valor))
        for j, d in enumerate((11, 26)):
            valor = _RESTAURANTE[(i + j) % len(_RESTAURANTE)]
            linhas.append((dia(d), "RESTAURANTE SABOR CASEIRO", valor))

    # A anomalia: no mês corrente, hoje mesmo — sempre dentro do período.
    linhas.append((hoje, "HOSPITAL CLINICA CENTRAL", "-1480.00"))
    return sorted(linha for linha in linhas if linha[0] <= hoje)


def escrever_extrato_demo(pasta: Path, hoje: date) -> Path:
    """Escreve o CSV sintético em `pasta` e devolve o caminho."""
    caminho = pasta / "extrato-demo.csv"
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["date", "description", "amount"])
        for quando, descricao, valor in linhas_demo(hoje):
            escritor.writerow([quando.isoformat(), descricao, valor])
    return caminho
