"""Execução da fila: classificar (modelo), decidir (código), executar (ToolBox via Gateway).

Por conversa: texto do cliente (só mensagens do cliente, mascarado, cortado) -> classify_fn ->
pedido resolvido -> Case como estava em `now` (fila: config.NOW; histórico: data_abertura)
-> decide() -> passos executados no papel atendente. O modelo só é chamado em classify_fn.
Qualquer exceção numa conversa vira acionar_pessoa com o TIPO do erro (nunca a mensagem) e
a fila continua. Depende só de Gateway (nunca de Dataset ou de CSV de dados).

classify_fn(texto_mascarado, conversation_id) -> Classificacao | Escalation.

Pedido usado (Review Focus 1 e 2): o vinculado à conversa (order_id) ou, se não houver, o
citado pelo classificador, que só vale se aparecer no texto do cliente (nunca inventar).
Pedido citado de outro cliente, ou vinculado de outro cliente -> pessoa, sem consulta ao
pedido no Case nem ação. Sem pedido nenhum e categoria que precisa dele -> pedir o número ao
cliente (responder_cliente), sem consultar pedido.

Log (Task 8): cada etapa (mascarar, classificar, consultar_pedido, decidir, executar; falha no
caminho de exceção) entra em CaseResult.log com o tempo em ms (time.perf_counter) e um resultado
curto gerado pelo código: categoria, status, ação, contagens. Nunca texto do cliente nem ids.
CaseResult.dados traz os fatos que justificaram a decisão (pipeline/fatos.py).
"""
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

from pipeline import executor
from pipeline.case_builder import build_case, conversa_e_agora
from pipeline.decide import (Case, Decision, decide, e_reacao_adversa,
                             reacao_adversa_sem_pedido)
from pipeline.fatos import fatos, sla as fato_sla
from pipeline.gateway import Gateway
from pipeline.mask import mask_text
from pipeline.models import Classificacao, Escalation
from pipeline.policy import Policy
from pipeline.sla import minutos_restantes

MAX_CHARS_CLASSIFICADOR = 4000
MAX_CONTEXTO = executor.MAX_CONTEXTO
AUTOR_CLIENTE = "cliente"
SEM_INTERACAO = "sem_interacao"  # politicas.csv: "o cliente não escreveu nada (só o bot falou)"


@dataclass
class CaseResult:
    conversation_id: str
    canal: str
    prioridade: int
    classificacao: dict
    decisao: dict
    calls: list[dict]
    evidencias: list[dict]
    origem: str = "fila"
    data_abertura: str = ""
    sla_minutos_restantes: float | None = None  # None: já respondida ou canal sem SLA
    resposta_cliente: dict | None = None
    primeira_resposta_dada: bool = False  # data_primeira_resposta preenchida
    marca: str = ""
    dados: list[dict] = field(default_factory=list)  # [{rotulo, valor}] sem ids
    log: list[dict] = field(default_factory=list)  # [{etapa, resultado, ms}]


class Cronometro:
    """Marca o tempo de cada etapa (ms desde a marca anterior) numa lista de log."""

    def __init__(self, log: list[dict], relogio=time.perf_counter) -> None:
        self._log, self._relogio = log, relogio
        self._t = relogio()

    def marca(self, etapa: str, resultado: str) -> None:
        agora = self._relogio()
        self._log.append({"etapa": etapa, "resultado": resultado,
                          "ms": round(max(agora - self._t, 0.0) * 1000, 1)})
        self._t = agora


# Classificador escalou: termos de sintoma no texto mantêm o caminho de reação adversa
# (orientar suspensão + registro pendente). Regra em código, a confirmar com o Ian.
_SINTOMA = re.compile(r"alergi|inchad|irrita|coceira|cocei|ardend|ardeu|queimad|vermelhid|"
                      r"mancha|bolha|feridas?\b|rea[cç][aã]o", re.IGNORECASE)


def priority_key(item: CaseResult) -> tuple:
    """Ordem de atendimento da fila (spec: reação adversa e Reclame Aqui primeiro, depois SLA):
      1. reação adversa pela classificação (categoria, secundária ou sinal de risco);
      2. canal reclame_aqui (resposta pública, custo de R$ 42 por conversa);
      3. todo o resto;
    dentro de cada grupo, menos minutos restantes de SLA de primeira resposta primeiro
    (vencidos, negativos, antes). Conversa que já teve a primeira resposta
    (data_primeira_resposta preenchida) não tem SLA de primeira resposta pendente:
    sla_minutos_restantes = None e vai para o fim do grupo, como canal sem SLA; empate pelo id.
    """
    grupo = 0 if e_reacao_adversa(item.classificacao) else \
        1 if item.canal == "reclame_aqui" else 2
    sla = item.sla_minutos_restantes
    return (grupo, sla if sla is not None else float("inf"), item.conversation_id)


def _texto_cliente(mensagens: list[dict]) -> str:
    textos = [m["texto"] for m in mensagens if m.get("autor") == AUTOR_CLIENTE and m["texto"]]
    return mask_text("\n".join(textos))[:MAX_CHARS_CLASSIFICADOR]  # mascara antes de cortar


def _resultado_classificacao(cl: Classificacao | Escalation) -> str:
    if isinstance(cl, Escalation):
        return f"escalada: {cl.motivo}"
    return f"{cl.categoria} (confiança {cl.confianca:.2f})".replace(".", ",")


def _classificar(gw: Gateway, classify_fn, cid: str,
                 cron: Cronometro) -> tuple[Classificacao | Escalation, str]:
    texto = _texto_cliente(gw.get_mensagens(cid))
    cron.marca("mascarar", "ok" if texto.strip() else "sem texto do cliente")
    if not texto.strip():
        cl = Classificacao(SEM_INTERACAO, None, None, [], 1.0)
    else:
        cl = classify_fn(texto, cid)
    cron.marca("classificar", _resultado_classificacao(cl))
    return cl, texto


def _citado(cl: Classificacao, texto: str) -> str:
    oid = (cl.order_id or "").strip().upper()
    return oid if oid and re.search(rf"\b{re.escape(oid)}\b", texto, re.IGNORECASE) else ""


def _outro_cliente(oid: str) -> Decision:
    return executor.pessoa(f"O pedido {oid} pertence a outro cliente; nenhum dado do pedido "
                           "foi usado e nenhuma ação foi feita.", "pedido_de_outro_cliente",
                           area="supervisao")


def _resolver_pedido(gw: Gateway, conv: dict, cl: Classificacao,
                     texto: str) -> tuple[str, Decision | None]:
    """(order_id a usar, decisão antecipada ou None). A consulta aqui só confere o dono."""
    vinculado, citado = conv["order_id"], _citado(cl, texto)
    dono = conv["customer_id"]
    if citado and citado != vinculado:
        p = gw.get_pedido(citado)
        if p and p["customer_id"] != dono:
            return "", _outro_cliente(citado)
        if p and vinculado:
            return "", executor.pessoa(f"A conversa está vinculada ao pedido {vinculado} e "
                                       f"cita o pedido {citado}.", "pedido_divergente")
        if p:
            return citado, None
        if not vinculado:
            return "", Decision("responder_cliente", "responder_cliente", {},
                                "Pedido citado não localizado; pedir que o cliente confira.",
                                "pedido_nao_localizado", [])
    if vinculado:
        p = gw.get_pedido(vinculado)
        if p and p["customer_id"] != dono:
            return "", _outro_cliente(vinculado)
    return vinculado, None


def _decidir(gw, policy, cid, conv, now, cl, texto,
             cron: Cronometro) -> tuple[Decision, Case | None]:
    order_id, antecipada = _resolver_pedido(gw, conv, cl, texto)
    if antecipada:
        cron.marca("consultar_pedido", f"sem consulta ({antecipada.regra})")
        if e_reacao_adversa(cl):
            return reacao_adversa_sem_pedido(policy, antecipada.motivo), None
        return antecipada, None
    case = build_case(gw, cid, now, cl, order_id, policy)
    cron.marca("consultar_pedido", (case.pedido.get("status_entrega") or "sem status")
               if case.pedido else "sem pedido")
    d = decide(case, policy)
    if d.regra == "pedido_ausente" and not order_id:
        d = Decision("responder_cliente", "responder_cliente", {},
                     "Conversa sem pedido identificado; pedir o número ao cliente.",
                     "pedido_ausente", [])
    return d, case


def _dict_decisao(d: Decision) -> dict:
    return {"acao": d.acao, "ferramenta": d.ferramenta, "params": d.params,
            "motivo": d.motivo, "regra": d.regra}


def run_conversation(gw: Gateway, policy: Policy, classify_fn,
                     conversation_id: str) -> CaseResult:
    cid = conversation_id
    conv, now, origem = conversa_e_agora(gw, cid)
    abertura = datetime.fromisoformat(conv["data_abertura"])
    respondida = bool(conv.get("data_primeira_resposta"))
    sla = None if respondida else minutos_restantes(conv["canal"], abertura, now, policy)
    r = CaseResult(cid, conv["canal"], 0, {}, {}, [], [], origem, conv["data_abertura"], sla,
                   primeira_resposta_dada=respondida, marca=conv.get("marca", ""))
    cron = Cronometro(r.log)
    categoria, case = None, None
    try:
        cl, texto = _classificar(gw, classify_fn, cid, cron)
        if isinstance(cl, Escalation):
            r.classificacao = {"escalation": cl.motivo}
            d = executor.pessoa(f"Classificador não concluiu: {cl.motivo}.", "classificacao")
            if _SINTOMA.search(texto):
                r.classificacao["sinais_risco"] = ["reacao_adversa"]  # prioridade da fila
                d = reacao_adversa_sem_pedido(policy, d.motivo)
        else:
            r.classificacao, categoria = asdict(cl), cl.categoria
            executor.executar(gw, [executor.Passo("classificar_conversa", {
                "conversation_id": cid, "categoria": cl.categoria,
                "categoria_secundaria": cl.categoria_secundaria})], r.calls)
            d, case = _decidir(gw, policy, cid, conv, now, cl, texto, cron)
        cron.marca("decidir", d.acao)
        executor.completar_pessoa(d, cid, r.canal, categoria)
        if d.regra == "reacao_adversa":
            d.params["relato_em"] = abertura.isoformat()  # prazo de 24 h conta do relato
        pedido = case.pedido if case else None
        passos, r.resposta_cliente = executor.planejar(d, cid, pedido, policy, now)
        antes = len(r.calls)
        executor.executar(gw, passos, r.calls)
        novas = r.calls[antes:]
        executadas = sum(c["status"] == "executada" for c in novas)
        cron.marca("executar", f"{executadas} executadas, {len(novas) - executadas} pendentes")
    except Exception as e:  # isolamento: só o tipo, nunca a mensagem (pode ter PII/token)
        d, case = executor.pessoa(f"Falha ao processar a conversa ({type(e).__name__}); "
                                  "encaminhada a uma pessoa.", "falha_pipeline"), None
        executor.completar_pessoa(d, cid, r.canal, categoria)
        passos, r.resposta_cliente = executor.planejar(d, cid, None, policy, now)
        executor.executar_sem_falhar(gw, passos, r.calls)
        cron.marca("falha", type(e).__name__)
    r.dados = fatos(case, d, policy)
    situacao_sla = fato_sla(sla, respondida)
    if situacao_sla:
        r.dados.append(situacao_sla)
    r.decisao = _dict_decisao(d)
    r.evidencias = [{"kind": s.kind, "detail": s.detail} for s in d.evidencias]
    return r


def run_queue(gw: Gateway, policy: Policy, classify_fn) -> list[CaseResult]:
    resultados = [run_conversation(gw, policy, classify_fn, c["conversation_id"])
                  for c in gw.fila()]
    resultados.sort(key=priority_key)
    for i, r in enumerate(resultados, 1):
        r.prioridade = i
    return resultados


# A CLI (py -m pipeline.run) fica em pipeline/cli.py; reexportada aqui.
from pipeline.cli import classify_from_fallback, main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
