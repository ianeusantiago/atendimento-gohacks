"""Fatos do pedido que justificaram a decisão, como pares {rotulo, valor} em texto.

Só dados derivados do Case e da Decision (status, datas, dias, valor, limites, contagens);
nunca ids (pedido, cliente, conversa, transação), nome, endereço ou texto do cliente.
Vai para CaseResult.dados e de lá para o export público (pipeline/export.py).
"""
from pipeline.decide import COM_FOTO, LIMITE, Case, Decision
from pipeline.deadlines import business_days_between, days_since_delivery, promised_date
from pipeline.policy import Policy

# Categorias em que o prazo de dias corridos do recebimento (politicas.csv) decide.
COM_PRAZO = (*COM_FOTO, "arrependimento_cancelamento")
COM_SEPARACAO = ("alteracao_endereco", "arrependimento_cancelamento")


def rs(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _par(rotulo: str, valor) -> dict:
    return {"rotulo": rotulo, "valor": str(valor)}


def _ferramenta_financeira(d: Decision) -> str | None:
    if d.ferramenta in LIMITE:
        return d.ferramenta
    if d.ferramenta == "solicitar_aprovacao" and d.params.get("acao") in LIMITE:
        return d.params["acao"]
    return None


def fatos(case: Case | None, d: Decision, policy: Policy) -> list[dict]:
    if case is None or not case.pedido:
        return []
    pedido, hoje = case.pedido, case.now.date()
    categoria = case.classificacao.categoria
    saida = [_par("Status do pedido", pedido.get("status_entrega") or "sem status"),
             _par("Valor do pedido", rs(case.valor))]
    try:
        prometido = promised_date(pedido, policy)
    except (KeyError, ValueError):
        prometido = None
    dias = days_since_delivery(pedido, case.now)
    entregue = dias is not None and dias >= 0
    if prometido and not entregue:
        saida.append(_par("Data prometida", prometido.isoformat()))
        if hoje > prometido:
            saida.append(_par("Dias úteis de atraso",
                              business_days_between(prometido, hoje, policy.feriados)))
    if entregue:
        saida.append(_par("Dias desde a entrega", dias))
        if categoria in COM_PRAZO:
            saida.append(_par("Prazo da política (dias corridos)", policy.prazo_dias))
    if case.dias_uteis_sem_movimento is not None:
        saida.append(_par("Dias úteis sem movimento no rastreio", case.dias_uteis_sem_movimento))
    if categoria in COM_SEPARACAO:
        saida.append(_par("Pedido separado", "sim" if pedido.get("data_separacao") else "não"))
    if categoria in COM_FOTO:
        saida.append(_par("Fotos no pedido (inclui outras conversas)", len(case.anexos)))
    financeira = _ferramenta_financeira(d)
    if financeira:
        saida.append(_par("Limite do atendente", rs(getattr(policy, LIMITE[financeira]))))
    return saida


def sla(minutos: float | None, respondida: bool) -> dict | None:
    """Situação do SLA de primeira resposta, ou None para canal sem SLA."""
    if respondida:
        return _par("SLA de primeira resposta", "já respondida")
    if minutos is None:
        return None
    if minutos < 0:
        return _par("SLA de primeira resposta", f"vencido há {round(-minutos)} min")
    return _par("SLA de primeira resposta", f"{round(minutos)} min restantes")
