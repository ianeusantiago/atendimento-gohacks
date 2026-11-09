"""Pedido e eventos como estavam numa data (decisão do Ian: histórico é avaliado na data da
conversa, data_abertura, e não no retrato de 02/11; fila usa config.NOW).

pedidos.csv é um retrato tirado em config.NOW: status_entrega é o estado final e só as datas
de separação e de entrega dizem quando cada etapa aconteceu. Antes do retrato o status é
derivado só dessas datas:
  entregue              se data_entrega <= as_of (data sem hora: conta o dia inteiro);
  em_transito           senão, se data_separacao <= as_of;
  aguardando_separacao  senão.
cancelado, devolvido e extraviado não têm data própria nos dados (devolvido traz a data da
entrega, não a da devolução), então só valem a partir do retrato; antes dele cairiam numa
data inventada. Datas posteriores a as_of ficam em branco. status_pagamento e os demais
campos do retrato não são alterados (decide() não os usa).
"""
from datetime import date, datetime

from pipeline.config import NOW


def _data_hora(valor: str) -> datetime:
    return datetime.fromisoformat(valor)  # aceita "AAAA-MM-DD" e "AAAA-MM-DD HH:MM:SS"


def pedido_as_of(pedido: dict, as_of: datetime, retrato: datetime = NOW) -> dict:
    p = dict(pedido)
    if as_of >= retrato:
        return p
    entrega, separacao = p.get("data_entrega"), p.get("data_separacao")
    entregue = bool(entrega) and date.fromisoformat(entrega[:10]) <= as_of.date()
    separado = bool(separacao) and _data_hora(separacao) <= as_of
    if not entregue:
        p["data_entrega"] = ""
    if not separado:
        p["data_separacao"] = ""
    p["status_entrega"] = ("entregue" if entregue else
                           "em_transito" if separado else "aguardando_separacao")
    return p


def eventos_ate(rows: list[dict], as_of: datetime, campo: str) -> list[dict]:
    """Linhas cujo `campo` (data) é <= as_of. Linha sem data fica de fora: não dá para
    afirmar que já tinha acontecido."""
    return [r for r in rows if r.get(campo) and _data_hora(r[campo]) <= as_of]


def anexos_ate(anexos: list[dict], conversation_id: str, as_of: datetime) -> list[dict]:
    """Anexos visíveis ao decidir a conversa em as_of (R6e): os da própria conversa sempre
    (são conteúdo da conversa em decisão, mesmo enviados depois da abertura); os de outras
    conversas só se enviado_em <= as_of. Serve de base para comparar hash_perceptual e,
    filtrada pelo pedido, de anexos do Case. Na fila (as_of = NOW) não corta nada."""
    return [a for a in anexos if a["conversation_id"] == conversation_id
            or (a["enviado_em"] and _data_hora(a["enviado_em"]) <= as_of)]
