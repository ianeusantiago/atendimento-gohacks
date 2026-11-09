from datetime import date, datetime

import pytest

from pipeline.config import NOW
from pipeline.data import read_csv
from pipeline.deadlines import (add_business_days, business_days_between,
                                days_since_delivery, promised_date)
from pipeline.policy import load_policy


def _pedido(**campos):
    """Pedido sintetico: so os campos que a regra de prazo usa."""
    base = {"marca": "Belleza", "personalizacao": "", "transportadora": "TransLeste",
            "uf": "SP", "data_pedido": "2026-10-30", "data_entrega": ""}
    base.update(campos)
    return base


def test_add_business_days_pula_fim_de_semana_e_feriado():
    assert add_business_days(date(2026, 10, 30), 3, {date(2026, 11, 2)}) == date(2026, 11, 5)


def test_add_business_days_nao_conta_o_proprio_dia():
    # sexta + 1 dia util = segunda
    assert add_business_days(date(2026, 10, 23), 1, set()) == date(2026, 10, 26)


def test_promised_date_belleza_sp_transleste():
    # preparo 1 + SLA TransLeste/SE 2 = 3 dias uteis depois de 30/10 (02/11 e feriado)
    assert promised_date(_pedido(), load_policy()) == date(2026, 11, 5)


def test_promised_date_modaviva_personalizado_usa_preparo_3():
    p = _pedido(marca="Modaviva", personalizacao="nome")
    # 3 + 2 = 5 dias uteis: 03, 04, 05, 06, 09/11
    assert promised_date(p, load_policy()) == date(2026, 11, 9)


def test_promised_date_modaviva_sem_personalizacao_usa_preparo_1():
    p = _pedido(marca="Modaviva", personalizacao="")
    assert promised_date(p, load_policy()) == date(2026, 11, 5)


def test_days_since_delivery_sem_entrega_e_none():
    assert days_since_delivery(_pedido(data_entrega=""), NOW) is None


def test_days_since_delivery_conta_dias_corridos():
    assert days_since_delivery(_pedido(data_entrega="2026-10-27"), NOW) == 6


def test_business_days_between_conta_depois_de_a_ate_b():
    # 30/10 (sex) -> 05/11 (qui), com 02/11 feriado: 03, 04, 05
    assert business_days_between(date(2026, 10, 30), date(2026, 11, 5), {date(2026, 11, 2)}) == 3
    assert business_days_between(date(2026, 11, 5), date(2026, 11, 5), set()) == 0


def test_promised_date_coincide_com_data_prometida_nos_dados():
    policy = load_policy()
    pedidos = [p for p in read_csv("pedidos.csv") if p["data_prometida"]]
    assert pedidos, "nenhum pedido com data_prometida"
    iguais = sum(promised_date(p, policy) == date.fromisoformat(p["data_prometida"][:10])
                 for p in pedidos)
    taxa = iguais / len(pedidos)
    assert taxa >= 0.95, f"coincidencia {taxa:.2%} ({iguais}/{len(pedidos)})"
