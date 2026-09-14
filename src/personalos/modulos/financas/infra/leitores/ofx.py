"""Leitor de extratos OFX/QFX via ofxparse."""
from __future__ import annotations

from decimal import Decimal

from ofxparse import OfxParser

from personalos.modulos.financas.aplicacao.portas import TransacaoBruta
from personalos.modulos.financas.dominio.dinheiro import Dinheiro


class LeitorOFX:
    def ler(self, caminho: str) -> list[TransacaoBruta]:
        try:
            with open(caminho, "rb") as f:
                ofx = OfxParser.parse(f)
            out: list[TransacaoBruta] = []
            for conta in ofx.accounts:
                for t in conta.statement.transactions:
                    out.append(
                        TransacaoBruta(
                            data=t.date.date(),
                            valor=Dinheiro.de_decimal(Decimal(str(t.amount))),
                            descricao=(t.memo or t.payee or "").strip(),
                            conta=str(conta.account_id),
                            fit_id=str(t.id) if t.id else None,
                        )
                    )
            return out
        except Exception as e:
            raise ValueError(f"{caminho}: {e}") from e
