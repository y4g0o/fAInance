"""Value Object Dinheiro — sempre em centavos (int). Nunca float."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


@dataclass(frozen=True, slots=True)
class Dinheiro:
    centavos: int

    @classmethod
    def de_centavos(cls, n: int) -> "Dinheiro":
        return cls(int(n))

    @classmethod
    def de_decimal(cls, d: Decimal) -> "Dinheiro":
        cents = (d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return cls(int(cents))

    @classmethod
    def de_texto(cls, s: str) -> "Dinheiro":
        """Aceita formato BR ('1.234,56') e US ('1234.56'). Trata 'R$' e sinal."""
        t = s.strip().replace(" ", "").replace("R$", "")
        if not t:
            raise ValueError("valor vazio")
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        elif t.rfind(".") > t.rfind(","):
            t = t.replace(",", "")
        try:
            return cls.de_decimal(Decimal(t))
        except (InvalidOperation, ArithmeticError) as e:
            raise ValueError(f"valor invalido: {s!r}") from e

    def __add__(self, outro: "Dinheiro") -> "Dinheiro":
        return Dinheiro(self.centavos + outro.centavos)

    def __sub__(self, outro: "Dinheiro") -> "Dinheiro":
        return Dinheiro(self.centavos - outro.centavos)

    def formatar(self) -> str:
        sinal = "-" if self.centavos < 0 else ""
        inteiro, cent = divmod(abs(self.centavos), 100)
        milhar = f"{inteiro:,}".replace(",", ".")
        return f"{sinal}R$ {milhar},{cent:02d}"
