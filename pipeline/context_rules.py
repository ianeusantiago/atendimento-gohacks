"""Fatos do contexto do pedido (reenvios, itens, pagamentos, estornos) que mudam a decisão.

Funções puras sobre as listas de Case, já cortadas em `now` (pipeline/asof.py): devolvem o
fato encontrado e decide.py monta a Decision. Nenhum texto daqui acusa o cliente.
"""
from datetime import datetime

# Status de pagamentos_gateway.csv em que o valor chegou a ser cobrado. "estornada" é o
# estado no retrato de 02/11: se o estorno ainda não estava processado em `now`, a
# transação estava cobrada naquele momento.
COBRADAS = ("capturada", "paga", "estornada")


def _brinde(item: dict) -> bool:
    return item["tipo_item"] == "brinde" or float(item["preco_unitario"]) == 0


def brinde_nao_coberto(reenvios: list[dict], itens: list[dict]) -> tuple[dict, str] | None:
    """(reenvio anterior mais recente, SKU do brinde) quando houve reenvio do pedido e nenhum
    reenvio levou o brinde (item de preço zero). Só tipo "reenvio": troca e nova produção
    mandam outro produto ou reimprimem, não repõem item faltante."""
    anteriores = [r for r in reenvios if r["tipo"] == "reenvio"]
    if not anteriores:
        return None
    enviados = {r["sku_enviado"] for r in anteriores}
    faltando = [i["sku"] for i in itens if _brinde(i) and i["sku"] not in enviados]
    if not faltando:
        return None
    return max(anteriores, key=lambda r: r["data_solicitacao"]), faltando[0]


def cobrancas_em_aberto(pagamentos: list[dict], estornos: list[dict],
                        now: datetime) -> list[dict]:
    """Transações cobradas em `now` sem estorno concluído e processado até `now`, na ordem
    de criação. Duas ou mais = cobrança duplicada ainda em aberto."""
    estornadas = {e["transacao_id"] for e in estornos
                  if e["status"] == "concluido" and e["data_hora_processamento"]
                  and datetime.fromisoformat(e["data_hora_processamento"]) <= now}
    abertas = [t for t in pagamentos
               if t["status"] in COBRADAS and t["transacao_id"] not in estornadas
               and t["data_hora_confirmacao"]
               and datetime.fromisoformat(t["data_hora_confirmacao"]) <= now]
    return sorted(abertas, key=lambda t: t["data_hora_criacao"])
