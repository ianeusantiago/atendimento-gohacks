"""Da Decision às chamadas de ferramenta, no papel atendente, via Gateway.

planejar() traduz a decisão em passos com os parâmetros exatos de ferramentas.csv
(conversation_id entra em toda ferramenta que o lista). Passo com `pendente` não é executado:
fica registrado para quem pode (ex.: registrar_cosmetovigilancia é só do supervisor) ou
aguarda um dado que o agente não tem (escolha do cliente, código do cupom, endereço novo, que
está no texto livre do cliente e não é extraído; o produto novo da troca). A resposta ao cliente vem de respostas.py;
quando a ferramenta principal não fala com o cliente, um responder_cliente leva o texto.
d.params["acoes_previas"] (ex.: validar_cupom antes de acionar_pessoa em cupom ambíguo) vira
passos ANTES da ferramenta principal, com a mesma regra de pendência.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from pipeline import respostas
from pipeline.decide import Decision
from pipeline.gateway import Gateway
from pipeline.mask import mask_text
from pipeline.policy import Policy
from pipeline.tools import FERRAMENTAS, permitido

PAPEL = "atendente"
MAX_CONTEXTO = 300
# Ferramentas que já falam com o cliente (ferramentas.csv): não precisam de responder_cliente.
FALAM_COM_CLIENTE = {"responder_cliente", "informar_status", "solicitar_foto",
                     "negar_por_politica", "agradecer", "orientar_suspensao_uso",
                     "responder_duvida"}
ASSUNTOS = {
    "reacao_adversa": "Reação adversa: registrar cosmetovigilância",
    "pedido_de_outro_cliente": "Pedido citado pertence a outro cliente",
    "pedido_divergente": "Conversa cita pedido diferente do vinculado",
    "classificacao": "Classificação automática não concluída",
    "falha_pipeline": "Falha ao processar a conversa",
    "confianca_minima": "Classificação incerta",
    "caso_sensivel": "Caso sensível",
    "pedido_ausente": "Pedido não encontrado",
}
URGENTES = {"reacao_adversa"}


@dataclass
class Passo:
    ferramenta: str
    params: dict
    pendente: str | None = None  # motivo de não executar agora
    papel: str = PAPEL
    prazo: datetime | None = None


def pessoa(motivo: str, regra: str, area: str = "supervisao", **params) -> Decision:
    return Decision("acionar_pessoa", "acionar_pessoa", {"area": area, **params}, motivo,
                    regra, [])


def contexto(motivo: str) -> str:
    """Contexto curto e factual para a pessoa: o motivo gerado pelo código (sem texto do
    cliente), mascarado por defesa e cortado em MAX_CONTEXTO."""
    texto = mask_text(motivo)
    return texto if len(texto) <= MAX_CONTEXTO else texto[:MAX_CONTEXTO - 1] + "…"


def completar_pessoa(d: Decision, conversation_id: str, canal: str, categoria: str | None):
    """acionar_pessoa sempre leva area, assunto, contexto e urgência (ferramentas.csv)."""
    if d.ferramenta != "acionar_pessoa":
        return
    p = d.params
    p.setdefault("area", "supervisao")
    p.setdefault("assunto", f"Conversa {conversation_id}: "
                            f"{ASSUNTOS.get(d.regra, categoria or d.regra)}")
    p.setdefault("contexto", contexto(d.motivo))
    urgente = d.regra in URGENTES or categoria in URGENTES or canal == "reclame_aqui"
    p.setdefault("urgencia", "alta" if urgente else "normal")


def _params(ferramenta: str, fonte: dict) -> dict:
    """Só os parâmetros que a ferramenta tem em ferramentas.csv, sem vazios."""
    return {k: fonte[k] for k in FERRAMENTAS[ferramenta].parametros
            if fonte.get(k) not in (None, "", [])}


def _reacao_adversa(d: Decision, cid: str, pedido: dict | None, now: datetime) -> list[Passo]:
    horas = d.params.get("prazo_registro_horas", 24)
    # O prazo conta do relato do cliente (verificação item 3a); sem ele, do "agora".
    relato = d.params.get("relato_em")
    inicio = datetime.fromisoformat(relato) if relato else now
    produto = pedido.get("descricao_produto", "") if pedido else ""
    registro = {"conversation_id": cid, "sku": pedido.get("sku") if pedido else None,
                "lote": pedido.get("lote_produto") if pedido else None,
                "descricao": f"Relato de reação adversa ao produto {produto}".strip()}
    falta = [] if registro["sku"] else ["sku (pedido não identificado)"]
    motivo = "registro exclusivo do supervisor (ferramentas.csv)"
    if inicio + timedelta(hours=horas) < now:
        motivo += "; PRAZO VENCIDO, registrar imediatamente"
    if falta:
        motivo += "; falta " + ", ".join(falta)
    return [Passo("orientar_suspensao_uso", {"conversation_id": cid}),
            Passo("acionar_pessoa", _params("acionar_pessoa", d.params)),
            Passo("registrar_cosmetovigilancia", _params("registrar_cosmetovigilancia", registro),
                  pendente=motivo, papel="supervisor", prazo=inicio + timedelta(hours=horas))]


PENDENCIA_SEM_DADO = {"validar_cupom": "aguarda o código do cupom"}


def _pendencia(d: Decision) -> str | None:
    if d.ferramenta in PENDENCIA_SEM_DADO:
        return PENDENCIA_SEM_DADO[d.ferramenta]
    if d.ferramenta == "reenviar_produto" and d.regra == "atraso_entrega":
        return "aguarda a escolha do cliente entre as opções da política"
    if d.ferramenta == "alterar_endereco":
        return "novo_endereco está no texto do cliente; o agente não extrai endereço"
    if d.ferramenta == "trocar_produto":
        # 1 troca por pedido (politicas.csv): não consumir a troca sem o produto novo.
        return "aguarda a escolha do novo produto"
    return None


def planejar(d: Decision, conversation_id: str, pedido: dict | None, policy: Policy,
             now: datetime) -> tuple[list[Passo], dict | None]:
    """(passos, resposta_cliente). resposta_cliente = {"texto", "enviada"} ou None."""
    texto = respostas.compor(d, pedido, policy, now)
    if d.regra == "reacao_adversa":
        passos = _reacao_adversa(d, conversation_id, pedido, now)
    else:
        fonte = {"conversation_id": conversation_id, "justificativa": contexto(d.motivo),
                 "motivo": d.params.get("motivo") or d.regra, "texto": texto, **d.params}
        if d.ferramenta == "encerrar_conversa":
            fonte["motivo"] = d.regra
        previas = [Passo(t, _params(t, fonte), pendente=PENDENCIA_SEM_DADO.get(t))
                   for t in d.params.get("acoes_previas", [])]
        passos = previas + [Passo(d.ferramenta, _params(d.ferramenta, fonte),
                                  pendente=_pendencia(d))]
    if d.ferramenta == "sinalizar_suspeita":
        # Não envia nada ao cliente; texto só para quando ele perguntar durante a análise.
        return passos, {"texto": respostas.em_analise(policy), "enviada": False}
    if texto is None:
        return passos, None
    if passos[0].ferramenta not in FALAM_COM_CLIENTE:
        passos.append(Passo("responder_cliente", {"conversation_id": conversation_id,
                                                  "texto": texto}))
    return passos, {"texto": texto, "enviada": True}


def _pendente(p: Passo, motivo: str) -> dict:
    return {"tool": p.ferramenta, "params": p.params, "role": p.papel, "status": "pendente",
            "motivo": motivo, "prazo": p.prazo.isoformat() if p.prazo else None}


def executar(gw: Gateway, passos: list[Passo], calls: list[dict]) -> None:
    """Executa os passos em ordem, acrescentando em `calls` (fica o que já foi feito se um
    passo falhar; a exceção sobe para o run_conversation)."""
    for p in passos:
        if p.pendente or not permitido(PAPEL, p.ferramenta):
            calls.append(_pendente(p, p.pendente or f"{p.ferramenta} não é do papel {PAPEL}"))
            continue
        call = gw.executar(p.ferramenta, **p.params)
        calls.append({**call, "status": "executada"})


def executar_sem_falhar(gw: Gateway, passos: list[Passo], calls: list[dict]) -> None:
    """Para o caminho de falha: o que não puder ser executado fica pendente."""
    for p in passos:
        try:
            executar(gw, [p], calls)
        except Exception as e:  # só o tipo: a mensagem pode trazer dado sensível
            calls.append(_pendente(p, f"falha ao executar ({type(e).__name__})"))
