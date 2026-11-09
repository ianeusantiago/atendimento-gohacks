"""Prazos: dias uteis, data prometida e dias desde a entrega.

Regra (politicas.csv, prazos_entrega): prazo prometido = data do pedido + preparo + SLA
da transportadora, em dias uteis (segunda a sexta, fora os feriados da politica),
contando a partir do primeiro dia util depois do pedido.
"""
from datetime import date, datetime, timedelta

from pipeline.policy import Policy

MARCA_MODAVIVA = "Modaviva"  # as demais marcas de pedidos.csv sao da Belleza


def _util(d: date, holidays: set[date]) -> bool:
    return d.weekday() < 5 and d not in holidays


def add_business_days(start: date, n: int, holidays: set[date]) -> date:
    """n-esimo dia util depois de start (start nao conta)."""
    d = start
    while n > 0:
        d += timedelta(days=1)
        if _util(d, holidays):
            n -= 1
    return d


def business_days_between(a: date, b: date, holidays: set[date]) -> int:
    """Dias uteis depois de a ate b, inclusive. 0 quando b <= a."""
    total, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if _util(d, holidays):
            total += 1
    return total


def preparo_key(pedido: dict) -> str:
    if pedido["marca"] != MARCA_MODAVIVA:
        return "belleza"
    return "modaviva_personalizado" if pedido["personalizacao"] else "modaviva_sem_personalizacao"


def promised_date(pedido: dict, policy: Policy) -> date:
    regiao = policy.regiao_por_uf[pedido["uf"]]
    dias = policy.preparo[preparo_key(pedido)] + policy.sla[(pedido["transportadora"], regiao)]
    return add_business_days(date.fromisoformat(pedido["data_pedido"][:10]), dias,
                             policy.feriados)


def days_since_delivery(pedido: dict, now: datetime) -> int | None:
    if not pedido.get("data_entrega"):
        return None
    return (now.date() - date.fromisoformat(pedido["data_entrega"][:10])).days
