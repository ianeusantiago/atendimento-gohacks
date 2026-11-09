"""Monta o decide.Case de uma conversa (fila ou histórico) como ela estava, só via Gateway.

Decisão do Ian: histórico é avaliado na data da conversa (data_abertura), não no retrato de
02/11; fila usa config.NOW. Pedido, reenvios, pagamentos e estornos são cortados em `now`
(pipeline/asof.py). Anexos (R6e, asof.anexos_ate): os da própria conversa entram sempre; os
de outras conversas só se enviados até `now`. O mesmo corte vale para a base de comparação de
hash_perceptual (todos_anexos) e para os anexos do pedido.

Rastreio parado (politicas.csv onde_esta_pedido: "Rastreio parado há 3 dias úteis ou mais"):
dias úteis entre o último evento do portal até `now` e `now`, quando esse evento não é final
(entregue ou extraviado). Sem evento até `now`, fica None (não dá para afirmar que parou).

Implementação única: o pipeline (run.py) e os testes (tests/helpers.py) usam este módulo.
"""
from datetime import datetime

from pipeline.asof import anexos_ate, eventos_ate
from pipeline.config import NOW
from pipeline.deadlines import business_days_between
from pipeline.decide import Case
from pipeline.gateway import Gateway
from pipeline.models import Classificacao
from pipeline.policy import Policy

STATUS_FINAIS_RASTREIO = ("entregue", "extraviado")


def conversa_e_agora(gw: Gateway, conversation_id: str) -> tuple[dict, datetime, str]:
    """(conversa, now, origem): origem "fila" usa config.NOW; "historico" usa data_abertura."""
    conv = gw.get_conversa(conversation_id)
    if conv is None:
        raise KeyError("conversa inexistente")
    if any(c["conversation_id"] == conversation_id for c in gw.fila()):
        return conv, NOW, "fila"
    return conv, datetime.fromisoformat(conv["data_abertura"]), "historico"


def dias_sem_movimento(eventos: list[dict], now: datetime, policy: Policy) -> int | None:
    """Dias úteis desde o último evento (já cortado em `now`); None se não há evento ou se o
    último é final."""
    if not eventos:
        return None
    ultimo = max(eventos, key=lambda e: datetime.fromisoformat(e["data_hora_evento"]))
    if ultimo["status"] in STATUS_FINAIS_RASTREIO:
        return None
    return business_days_between(datetime.fromisoformat(ultimo["data_hora_evento"]).date(),
                                 now.date(), policy.feriados)


def build_case(gw: Gateway, conversation_id: str, now: datetime, cl: Classificacao,
               order_id: str, policy: Policy) -> Case:
    """Case com o pedido `order_id` (vazio = sem pedido: nada do pedido é consultado)."""
    conv = gw.get_conversa(conversation_id)
    pedido = gw.get_pedido(order_id, as_of=now) if order_id else None
    base = anexos_ate(gw.todos_anexos(), conversation_id, now)
    proprios = [a for a in base if a["conversation_id"] == conversation_id]
    outros = [a for a in base
              if order_id and a["order_id"] == order_id
              and a["conversation_id"] != conversation_id]

    def _do_pedido(buscar, campo):
        return eventos_ate(buscar(order_id), now, campo) if pedido else []

    return Case(
        classificacao=cl, pedido=pedido,
        cliente=gw.get_cliente(conv["customer_id"]) if conv else None,
        anexos=proprios + outros, todos_anexos=base,
        valor=float(pedido["valor"]) if pedido else 0.0, now=now,
        dias_uteis_sem_movimento=(dias_sem_movimento(gw.get_rastreio(order_id, as_of=now), now,
                                                     policy) if pedido else None),
        reenvios_anteriores=_do_pedido(gw.get_reenvios, "data_solicitacao"),
        pagamentos=_do_pedido(gw.get_pagamentos, "data_hora_criacao"),
        estornos=_do_pedido(gw.get_estornos, "data_hora_solicitacao"),
        itens=gw.get_itens(order_id) if pedido else [],
    )
