"""Gráfico de barras em SVG gerado no servidor.

Por que não uma biblioteca de gráfico: seriam ~200 KB de JavaScript versionados
para desenhar barras, num projeto cujo valor declarado é sobreviver dez anos sem
toolchain. Isto são ~60 linhas, funciona com JavaScript desligado, não tem asset
para envelhecer e é testável como função pura. Ver ADR 0007.

Recebe valores em CENTAVOS e só divide por 100 na hora de escrever o rótulo —
nenhuma aritmética de dinheiro acontece aqui.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from html import escape

LARGURA = 720
ALTURA = 220
MARGEM_BAIXO = 28
MARGEM_TOPO = 12


@dataclass(frozen=True)
class Serie:
    rotulo: str
    valores: Sequence[int]  # centavos, sempre magnitude positiva
    classe: str  # classe CSS, para a cor viver na folha de estilo


def barras(meses: Sequence[str], series: Sequence[Serie]) -> str:
    """SVG de barras agrupadas. Devolve string vazia se não há o que desenhar."""
    if not meses or not series:
        return ""
    teto = max((max(s.valores, default=0) for s in series), default=0)
    if teto <= 0:
        return ""

    altura_util = ALTURA - MARGEM_BAIXO - MARGEM_TOPO
    largura_grupo = LARGURA / len(meses)
    largura_barra = largura_grupo / (len(series) + 1)
    partes = [
        f'<svg viewBox="0 0 {LARGURA} {ALTURA}" role="img" '
        f'aria-label="Fluxo mensal" class="grafico">'
    ]
    for indice_mes, mes in enumerate(meses):
        base_x = indice_mes * largura_grupo
        for indice_serie, serie in enumerate(series):
            valor = serie.valores[indice_mes] if indice_mes < len(serie.valores) else 0
            altura = (valor / teto) * altura_util
            x = base_x + largura_barra * (indice_serie + 0.5)
            y = MARGEM_TOPO + (altura_util - altura)
            partes.append(
                f'<rect class="{escape(serie.classe)}" x="{x:.1f}" y="{y:.1f}" '
                f'width="{largura_barra * 0.9:.1f}" height="{max(altura, 0):.1f}">'
                f"<title>{escape(mes)} — {escape(serie.rotulo)}: "
                f"R$ {valor / 100:,.2f}</title></rect>"
            )
        partes.append(
            f'<text class="rotulo-x" x="{base_x + largura_grupo / 2:.1f}" '
            f'y="{ALTURA - 8}" text-anchor="middle">{escape(mes[5:])}</text>'
        )
    partes.append("</svg>")
    return "".join(partes)
