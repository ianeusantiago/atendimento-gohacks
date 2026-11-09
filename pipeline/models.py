"""Saidas do classificador: uma classificacao validada ou um pedido de escalada para pessoa."""
from dataclasses import dataclass, field


@dataclass
class Classificacao:
    categoria: str
    categoria_secundaria: str | None
    order_id: str | None
    sinais_risco: list[str] = field(default_factory=list)
    confianca: float = 0.0


@dataclass
class Escalation:
    motivo: str
