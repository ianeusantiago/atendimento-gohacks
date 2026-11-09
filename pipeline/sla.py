"""SLA de primeira resposta por canal (politicas.csv, sla_primeira_resposta).

Prazo = data_abertura + SLA do canal (`<canal>.minutos` ou `<canal>.horas`). Quando
`<canal>.conta_apenas_horario_comercial` é True, só contam os minutos dentro do horário de
atendimento humano (horario_atendimento_humano.inicio/fim; "todos os dias, inclusive
feriados", então não há dia pulado).
"""
from datetime import datetime, time, timedelta

from pipeline.policy import Policy


def _hora(valor: str) -> time:
    return time.fromisoformat(valor)


def _somar_no_horario(inicio_em: datetime, minutos: float, abre: time, fecha: time) -> datetime:
    t, resta = inicio_em, timedelta(minutes=minutos)
    while True:
        abertura = datetime.combine(t.date(), abre)
        fechamento = datetime.combine(t.date(), fecha)
        if t < abertura:
            t = abertura
        if t >= fechamento:
            t = datetime.combine(t.date() + timedelta(days=1), abre)
            continue
        if t + resta <= fechamento:
            return t + resta
        resta -= fechamento - t
        t = datetime.combine(t.date() + timedelta(days=1), abre)


def prazo_primeira_resposta(canal: str, abertura: datetime, policy: Policy) -> datetime:
    sla = policy.regras["sla_primeira_resposta"]
    if f"{canal}.minutos" in sla:
        minutos = float(sla[f"{canal}.minutos"])
    elif f"{canal}.horas" in sla:
        minutos = float(sla[f"{canal}.horas"]) * 60
    else:
        raise KeyError(f"canal sem SLA em politicas.csv: {canal}")
    if sla.get(f"{canal}.conta_apenas_horario_comercial") == "True":
        horario = policy.regras["horario_atendimento_humano"]
        return _somar_no_horario(abertura, minutos, _hora(horario["inicio"]),
                                 _hora(horario["fim"]))
    return abertura + timedelta(minutes=minutos)


def minutos_restantes(canal: str, abertura: datetime, now: datetime,
                      policy: Policy) -> float | None:
    """Minutos até o fim do SLA em `now` (negativo = vencido); None se o canal não tem SLA."""
    try:
        prazo = prazo_primeira_resposta(canal, abertura, policy)
    except KeyError:
        return None
    return round((prazo - now).total_seconds() / 60, 1)
