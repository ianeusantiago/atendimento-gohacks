"""Decisão de negócio em código: ação, alçada, prazo e suspeita. O modelo só classifica.

Precedência (plano, Global Constraints):
  1. reação adversa ou caso sensível -> pessoa;
  2. reclamação sinalizada (ao menos um sinal forte nos anexos) -> sinalizar_suspeita, sem ação
     financeira; sinais fracos sozinhos só acompanham a decisão normal como evidência;
  2b. contexto do pedido (pipeline/context_rules.py): reclamação física com reenvio anterior
     que não levou o brinde -> pessoa (nem foto nem prazo); arrependimento com cobrança
     duplicada ainda em aberto -> pessoa (dois reembolsos; a política não diz como somar);
  3. fora do prazo (dias corridos desde o recebimento > prazo da política) -> negar_por_politica
     (só com data de recebimento conhecida; decisão R6d, o prazo vem antes da foto);
  4. sem foto (categoria exige foto e não há anexo) -> solicitar_foto;
  5. alçada: acima do limite do atendente -> solicitar_aprovacao; senão a ferramenta da categoria.
cupom_promocao com sinal de ambiguidade do classificador (sem_politica_aplicavel,
duvida_elegibilidade_cupom) vai para pessoa; na dúvida de elegibilidade, validar_cupom vem
antes (params["acoes_previas"], executado pelo executor antes da ferramenta principal).
Reclamação física (atraso, avaria, item faltante, personalização) em pedido ainda não recebido
vira rastreio/atraso antes das etapas 3 e 4: não há produto para fotografar nem para reenviar.
Limites, prazos e textos de regra vêm de Policy (politicas.csv). Nenhum texto acusa o cliente.
"""
from dataclasses import dataclass, field
from datetime import date, datetime

from pipeline.context_rules import brinde_nao_coberto, cobrancas_em_aberto
from pipeline.deadlines import business_days_between, days_since_delivery, promised_date
from pipeline.evidence import SINAIS_FORTES, Signal, suspicion_signals
from pipeline.models import Classificacao
from pipeline.policy import Policy

# a confirmar: parâmetro de governança (não está em politicas.csv). Abaixo disso a
# classificação não é confiável o bastante para o código agir sozinho.
CONFIANCA_MINIMA = 0.6
# a confirmar: sinais_risco do classificador que tornam o caso sensível (vai para pessoa).
SINAIS_SENSIVEIS = ("ameaca_juridica",)
# onde_esta_pedido: politicas.csv traz este número só no texto da regra
# ("Rastreio parado há 3 dias úteis ou mais: abrir chamado"), sem campo próprio.
DIAS_UTEIS_RASTREIO_PARADO = 3

FISICAS = ("atraso_entrega", "avaria_vazamento", "item_faltante", "erro_personalizacao")
# Reclamação física sobre pedido devolvido ou cancelado vai para a logística (sem ferramenta
# financeira). Arrependimento não passa por aqui: usa só a data de entrega (N06, devolvido).
STATUS_SEM_ACAO_FISICA = ("devolvido", "cancelado")
SEM_PEDIDO = ("duvida_produto", "cupom_promocao", "elogio", "sem_interacao")
# Ferramenta financeira -> atributo de Policy com o limite do atendente.
LIMITE = {"reenviar_produto": "limite_reenvio", "reimprimir_personalizacao": "limite_reenvio",
          "trocar_produto": "limite_troca", "reembolsar": "limite_reembolso"}
# politicas.csv usa "encerrar_sem_acao"; a ferramenta em ferramentas.csv é encerrar_conversa.
FERRAMENTA_EQUIVALENTE = {"encerrar_sem_acao": "encerrar_conversa"}
# atraso_entrega: "reenviar ou reembolsar, à escolha do cliente".
OPCOES_ATRASO = ["reenvio", "reembolso"]
COM_FOTO = ("avaria_vazamento", "item_faltante", "erro_personalizacao")
DO_QUE_FOTOGRAFAR = {"erro_personalizacao": "personalização"}
COMUNICACAO_SUSPEITA = "solicitação em análise"
# Sinais de ambiguidade do classificador em cupom_promocao (o modelo só marca o sinal; a ação
# é decidida aqui). sem_politica_aplicavel: o cliente pede algo que nenhuma política cobre
# (ex.: desconto de Black Friday) -> pessoa. duvida_elegibilidade_cupom: dúvida de elegibilidade
# que os dados do cupom podem não resolver -> validar_cupom antes e depois pessoa.
SEM_POLITICA = "sem_politica_aplicavel"
DUVIDA_CUPOM = "duvida_elegibilidade_cupom"
INSTRUCAO = "instrucao_no_texto"
# Ferramentas que movem dinheiro: as de LIMITE e o cancelamento (estorno integral).
COM_DINHEIRO = set(LIMITE) | {"cancelar_pedido"}


@dataclass
class Case:
    """Contexto da decisão como estava em `now` (fila: config.NOW; histórico: data_abertura).

    pedido já vem cortado em `now` (pipeline/asof.pedido_as_of). anexos são do PEDIDO, não só
    da conversa: foto enviada em qualquer conversa do pedido até `now` satisfaz a exigência de
    foto (nunca pedir de novo). reenvios_anteriores, pagamentos e estornos já vêm filtrados
    para eventos datados até `now` (pipeline/asof.eventos_ate); itens são as linhas do pedido.
    """
    classificacao: Classificacao
    pedido: dict | None
    cliente: dict | None
    anexos: list[dict]
    todos_anexos: list[dict]
    valor: float
    now: datetime
    dias_uteis_sem_movimento: int | None = None  # rastreio parado (vem do Gateway)
    reenvios_anteriores: list[dict] = field(default_factory=list)  # trocas_reenvios.csv
    pagamentos: list[dict] = field(default_factory=list)  # pagamentos_gateway.csv
    estornos: list[dict] = field(default_factory=list)  # estornos.csv
    itens: list[dict] = field(default_factory=list)  # itens_pedido.csv


@dataclass
class Decision:
    acao: str  # o que o caso pede (mesmo formato de acao_esperada em evals/casos.csv)
    ferramenta: str | None  # ferramenta de ferramentas.csv que o agente chama
    params: dict
    motivo: str
    regra: str  # seção/categoria de politicas.csv que fundamenta a decisão
    evidencias: list[Signal] = field(default_factory=list)


def _dec(ferramenta: str, motivo: str, regra: str, /, **params) -> Decision:
    return Decision(ferramenta, ferramenta, params, motivo, regra, [])


def _pessoa(motivo: str, regra: str, /, area: str = "supervisao", **params) -> Decision:
    return _dec("acionar_pessoa", motivo, regra, area=area, **params)


def _acoes(policy: Policy, categoria: str) -> list[str]:
    valor = policy.categorias[categoria].get("acoes_permitidas", [])
    return valor if isinstance(valor, list) else [valor]


def _recebido(pedido: dict, now: datetime) -> bool:
    # Pedidos do histórico trazem a foto final: entrega depois do "agora" ainda não aconteceu.
    entrega = pedido.get("data_entrega")
    return bool(entrega) and date.fromisoformat(entrega[:10]) <= now.date()


def _separado(pedido: dict, now: datetime) -> bool:
    separacao = pedido.get("data_separacao")
    return bool(separacao) and datetime.fromisoformat(separacao) <= now


def _alcada(ferramenta: str, case: Case, policy: Policy, regra: str, motivo: str, /,
            **extra) -> Decision:
    limite = getattr(policy, LIMITE[ferramenta])
    params = {"order_id": case.pedido["order_id"], "valor": case.valor, **extra}
    if case.valor > limite:
        return _dec("solicitar_aprovacao",
                    f"{motivo} Valor R$ {case.valor:.2f} acima do limite do atendente "
                    f"(R$ {limite:.2f}): aprovação do supervisor.", regra,
                    acao=ferramenta, **params)
    return _dec(ferramenta, f"{motivo} Valor dentro do limite do atendente (R$ {limite:.2f}).",
                regra, **params)


def _negar(categoria: str, policy: Policy, motivo: str) -> Decision:
    return _dec("negar_por_politica", motivo, categoria,
                regra=policy.categorias[categoria].get("regra", ""))


def _reacao_adversa(policy: Policy) -> Decision:
    regra = policy.categorias["reacao_adversa"]
    obrigatorias = regra["acoes_obrigatorias"]
    horas = regra["prazo_registro_horas"]
    return Decision(";".join(obrigatorias), "acionar_pessoa",
                    {"area": "supervisao", "urgencia": "alta", "acoes_obrigatorias": obrigatorias,
                     "prazo_registro_horas": horas},
                    f"Relato de reação adversa: orientar a suspensão do uso e registrar em "
                    f"cosmetovigilância em até {horas} h; o registro é do supervisor.",
                    "reacao_adversa", [])


def _cupom_ambiguo(cl: Classificacao) -> Decision | None:
    if SEM_POLITICA in cl.sinais_risco:
        return _pessoa("Pedido de promoção ou desconto que nenhuma política cobre; uma pessoa "
                       "do comercial decide.", "cupom_promocao", area="comercial")
    if DUVIDA_CUPOM in cl.sinais_risco:
        d = _pessoa("Dúvida de elegibilidade do cupom que os dados do cupom podem não "
                    "resolver: validar o cupom e acionar uma pessoa do comercial.",
                    "cupom_promocao", area="comercial", acoes_previas=["validar_cupom"])
        d.acao = "validar_cupom;acionar_pessoa"
        return d
    return None


def _sinalizar(sinais: list[Signal]) -> Decision:
    kinds = list(dict.fromkeys(s.kind for s in sinais))
    return Decision("sinalizar_suspeita", "sinalizar_suspeita",
                    {"sinais": kinds, "evidencias": [s.detail for s in sinais],
                     "comunicacao_cliente": COMUNICACAO_SUSPEITA},
                    "Evidências dos anexos não conferem com o pedido; reenvio, troca e reembolso "
                    "ficam suspensos até a decisão do supervisor. Para o cliente: "
                    f"{COMUNICACAO_SUSPEITA}; nada é enviado agora.",
                    "reclamacao_suspeita", list(sinais))


def _nao_recebido(categoria: str, case: Case, policy: Policy) -> Decision:
    pedido, hoje = case.pedido, case.now.date()
    order_id = pedido["order_id"]
    extraviado = pedido.get("status_entrega") == "extraviado"
    prometido = promised_date(pedido, policy)
    atraso = business_days_between(prometido, hoje, policy.feriados)
    limite = policy.categorias["atraso_entrega"]["limite_dias_uteis_para_reenvio"]
    situacao = "extravio" if extraviado else f"atraso de {atraso} dias úteis"
    if categoria == "atraso_entrega" and (extraviado or atraso > limite):
        # Reembolso só entra como opção do cliente se couber na alçada de reembolso.
        if case.valor <= policy.limite_reembolso:
            extra, opcao = {"opcoes": OPCOES_ATRASO}, "reenvio ou reembolso, à escolha do cliente"
        else:
            extra = {"opcoes": ["reenvio"], "reembolso_exige_aprovacao": True}
            opcao = (f"reenvio; reembolso acima de R$ {policy.limite_reembolso:.2f} "
                     "exige aprovação do supervisor")
        return _alcada("reenviar_produto", case, policy, categoria,
                       f"Pedido não entregue, {situacao} (limite de {limite} dias úteis); "
                       f"{opcao}.", motivo=situacao, **extra)
    if not extraviado and hoje <= prometido:
        return _dec("informar_status", f"Pedido ainda não entregue e dentro do prazo prometido "
                                       f"({prometido.isoformat()}).", categoria, order_id=order_id)
    return _dec("abrir_chamado_transportadora",
                f"Pedido não entregue, {situacao} em relação a {prometido.isoformat()}.",
                categoria, order_id=order_id, motivo=situacao)


def _reclamacao_fisica(categoria: str, case: Case, policy: Policy,
                       sinais: list[Signal] = ()) -> Decision:
    status = case.pedido.get("status_entrega")
    if status in STATUS_SEM_ACAO_FISICA:
        # devolvido traz data_entrega; nem por isso cabe reenvio/reimpressão sem uma pessoa.
        return _pessoa(f"Reclamação sobre pedido com status {status}; a política não cobre.",
                       categoria, area="logistica", order_id=case.pedido["order_id"])
    if not _recebido(case.pedido, case.now):
        return _nao_recebido(categoria, case, policy)
    if categoria == "atraso_entrega":
        return _pessoa("Reclamação de atraso, mas o pedido consta como entregue.", categoria,
                       area="logistica", order_id=case.pedido["order_id"])
    regra = policy.categorias[categoria]
    # Prazo antes da foto (R6d): quem já passou do prazo ouve a política, sem pedido de foto.
    # Só com data de recebimento conhecida; sem ela a etapa é pulada.
    dias = days_since_delivery(case.pedido, case.now)
    if dias is not None and dias > policy.prazo_dias:
        return _negar(categoria, policy, f"Recebido há {dias} dias; o prazo da política é de "
                                         f"{policy.prazo_dias} dias corridos do recebimento.")
    if regra.get("exige_foto") and not case.anexos:
        return _dec("solicitar_foto", "A política exige foto para esta reclamação.", categoria,
                    do_que=DO_QUE_FOTOGRAFAR.get(categoria, "produto e embalagem"))
    ferramenta = next(a for a in _acoes(policy, categoria) if a in LIMITE)
    # Sinal fraco não bloqueia, mas também não deixa afirmar "foto coerente" (verificação item 2).
    foto = (f"Foto com sinal fraco para conferência "
            f"({', '.join(dict.fromkeys(s.kind for s in sinais))})" if sinais
            else "Foto coerente com o pedido")
    return _alcada(ferramenta, case, policy, categoria,
                   f"{foto}, recebido há {dias} dias (prazo "
                   f"{policy.prazo_dias}).", motivo=categoria)


def _contexto_do_pedido(categoria: str, case: Case, policy: Policy) -> Decision | None:
    order_id = case.pedido["order_id"]
    if categoria in COM_FOTO:
        achado = brinde_nao_coberto(case.reenvios_anteriores, case.itens)
        if achado:
            reenvio, sku = achado
            # area "qualidade": o reenvio saiu com o SKU errado (falha da operação, não do
            # cliente). ferramentas.csv lista qualidade entre as áreas de acionar_pessoa e
            # não lista "atendimento".
            return _pessoa(f"Reenvio {reenvio['solicitacao_id']} "
                           f"({reenvio['data_solicitacao'][:10]}) enviou "
                           f"{reenvio['sku_enviado']}; o brinde {sku} do pedido não saiu em "
                           "nenhum reenvio. Não pedir nova foto nem negar por prazo: a pendência "
                           "vem do reenvio anterior.", categoria, area="qualidade",
                           order_id=order_id, reenvio_anterior=reenvio["solicitacao_id"],
                           sku_reenviado=reenvio["sku_enviado"], sku_nao_coberto=sku)
    if categoria == "arrependimento_cancelamento":
        abertas = cobrancas_em_aberto(case.pagamentos, case.estornos, case.now)
        if len(abertas) >= 2:
            # Reembolso do arrependimento (valor do pedido) + estorno de cada cobrança a mais.
            valores = [case.valor] + [float(t["valor"]) for t in abertas[1:]]
            total, limite = round(sum(valores), 2), policy.limite_reembolso
            if total > limite:
                soma = (f"acima do limite de R$ {limite:.2f} por reembolso do atendente. A "
                        "política não diz se o limite vale por ação ou pela soma.")
            else:
                soma = (f"dentro do limite de R$ {limite:.2f}. A política não trata "
                        "duplicidade junto com arrependimento.")
            return _pessoa(f"Arrependimento com cobrança duplicada ainda em aberto "
                           f"({len(abertas)} transações cobradas, nenhum estorno processado): "
                           f"{len(valores)} reembolsos devidos, total R$ {total:.2f}, {soma}",
                           categoria, order_id=order_id, categoria_secundaria="cobranca_duplicada",
                           transacoes=[t["transacao_id"] for t in abertas],
                           valores_reembolso=valores, total_reembolso=total,
                           limite_reembolso=limite)
    return None


def _por_categoria(categoria: str, case: Case, policy: Policy,
                   sinais: list[Signal] = ()) -> Decision:
    pedido, now = case.pedido, case.now
    order_id = pedido["order_id"]
    if categoria == "onde_esta_pedido":
        parado = case.dias_uteis_sem_movimento
        if parado is not None and parado >= DIAS_UTEIS_RASTREIO_PARADO:
            return _dec("abrir_chamado_transportadora", f"Rastreio parado há {parado} dias úteis.",
                        categoria, order_id=order_id, motivo="rastreio parado")
        return _dec("informar_status", "Informar status e previsão do pedido.", categoria,
                    order_id=order_id)
    if categoria in FISICAS:
        return _reclamacao_fisica(categoria, case, policy, sinais)
    if categoria == "pagamento_pendente":
        return _dec(_acoes(policy, categoria)[0], "Consultar o pagamento no gateway.", categoria,
                    order_id=order_id)
    if categoria == "cobranca_duplicada":
        return _alcada("reembolsar", case, policy, categoria, "Estorno da cobrança duplicada.",
                       motivo="cobrança duplicada")
    if categoria == "alteracao_endereco":
        if _separado(pedido, now):
            return _negar(categoria, policy, "Pedido já separado; endereço não pode mudar.")
        return _dec("alterar_endereco", "Pedido ainda não separado.", categoria, order_id=order_id)
    if categoria == "arrependimento_cancelamento":
        if not _separado(pedido, now):
            return _dec("cancelar_pedido", "Pedido ainda não separado: cancelamento com estorno "
                                           "integral.", categoria, order_id=order_id)
        if not _recebido(pedido, now):
            return _pessoa("Arrependimento com pedido separado e ainda não recebido: a política "
                           "não cobre.", categoria, order_id=order_id)
        dias = days_since_delivery(pedido, now)
        if dias > policy.prazo_dias:
            return _negar(categoria, policy, f"Recebido há {dias} dias; prazo de "
                                             f"{policy.prazo_dias} dias do recebimento.")
        return _alcada("reembolsar", case, policy, categoria,
                       f"Arrependimento em {dias} dias do recebimento.", motivo="arrependimento")
    if categoria == "troca_fragrancia":
        if not _recebido(pedido, now):
            return _pessoa("Troca pedida antes do recebimento: a política não cobre.", categoria,
                           order_id=order_id)
        dias = days_since_delivery(pedido, now)
        prazo = policy.categorias[categoria]["prazo_dias_corridos_do_recebimento"]
        if dias > prazo:
            return _negar(categoria, policy, f"Recebido há {dias} dias; prazo de {prazo} dias.")
        return _alcada("trocar_produto", case, policy, categoria,
                       f"Troca em {dias} dias do recebimento (prazo {prazo}).")
    return _pessoa("Categoria sem regra de decisão no código.", categoria)


def e_reacao_adversa(cl: Classificacao | dict) -> bool:
    """Regra única (decisão e prioridade da fila). Aceita a Classificacao ou o dict dela."""
    c = cl if isinstance(cl, dict) else cl.__dict__
    return "reacao_adversa" in (c.get("categoria"), c.get("categoria_secundaria"),
                                *(c.get("sinais_risco") or []))


def reacao_adversa_sem_pedido(policy: Policy, motivo_pedido: str) -> Decision:
    """Reação adversa quando o pedido não pode ser usado (divergente ou de outro cliente):
    as ações obrigatórias continuam (verificação item 3b); o motivo do pedido vai junto."""
    d = _reacao_adversa(policy)
    d.motivo = f"{d.motivo} {motivo_pedido}"
    return d


def decide(case: Case, policy: Policy) -> Decision:
    cl = case.classificacao
    categoria = cl.categoria
    if e_reacao_adversa(cl):
        return _reacao_adversa(policy)
    sensiveis = [s for s in cl.sinais_risco if s in SINAIS_SENSIVEIS]
    if sensiveis:
        return _pessoa(f"Caso sensível ({', '.join(sensiveis)}).", "caso_sensivel")
    if cl.confianca < CONFIANCA_MINIMA:
        return _pessoa(f"Classificação incerta (confiança {cl.confianca:.2f} abaixo de "
                       f"{CONFIANCA_MINIMA}).", "confianca_minima", area="supervisao")
    if categoria not in policy.categorias:
        return _pessoa("Categoria fora de politicas.csv.", "categorias", area="supervisao")
    if categoria == "cupom_promocao":
        ambiguo = _cupom_ambiguo(cl)
        if ambiguo:
            return ambiguo
    if categoria in SEM_PEDIDO:
        acao = _acoes(policy, categoria)[0]
        return _dec(FERRAMENTA_EQUIVALENTE.get(acao, acao), "Ação da política para a categoria.",
                    categoria)
    if not case.pedido:
        return _pessoa("Pedido não identificado na conversa.", "pedido_ausente",
                       area="supervisao")
    sinais = []
    if set(_acoes(policy, categoria)) & set(LIMITE):
        sinais = suspicion_signals(case.anexos, case.pedido, case.todos_anexos)
        if any(s.kind in SINAIS_FORTES for s in sinais):
            return _sinalizar(sinais)
    decisao = (_contexto_do_pedido(categoria, case, policy)
               or _por_categoria(categoria, case, policy, sinais))
    decisao.evidencias = sinais  # só sinais fracos aqui: informativos, não bloqueiam
    if INSTRUCAO in cl.sinais_risco and decisao.ferramenta in COM_DINHEIRO:
        # Uma ordem no texto ("reembolse", JSON forjado) nunca dispara ferramenta financeira
        # sozinha (verificação item 7). Ferramentas não financeiras seguem normais (M01).
        return _pessoa(f"Mensagem traz instrução dirigida ao sistema; {decisao.ferramenta} não "
                       "é executado sozinho, uma pessoa confere o pedido.", decisao.regra,
                       area="supervisao", order_id=case.pedido["order_id"],
                       ferramenta_sugerida=decisao.ferramenta)
    return decisao
