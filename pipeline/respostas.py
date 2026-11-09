"""Respostas ao cliente montadas só com dados, por templates curtos (pt-BR).

Nenhum texto de modelo vai ao cliente. Os campos usados são do pedido (número, transportadora,
status, datas, valor) e da política (texto da regra de politicas.csv, citado sem mudar).
Nunca entram nome, CPF, telefone, cartão, endereço nem texto livre do cliente; nenhum template
acusa o cliente. sinalizar_suspeita não envia nada (ferramentas.csv: "Não envia nada ao
cliente"); em_analise() é o texto para quando o cliente perguntar durante a análise, conforme
politicas.csv reclamacao_suspeita.comunicacao_com_cliente.

compor() devolve None quando a própria ferramenta não fala com o cliente pelo agente
(encerrar_conversa, sinalizar_suspeita, responder_duvida: esta responde pela ficha do produto,
que não está nos dados).
"""
from datetime import date, datetime

from pipeline.config import NOW
from pipeline.deadlines import promised_date
from pipeline.decide import Decision
from pipeline.policy import Policy

STATUS = {"aguardando_separacao": "em preparação para envio", "em_transito": "em trânsito",
          "entregue": "entregue", "extraviado": "com extravio informado pela transportadora",
          "cancelado": "cancelado", "devolvido": "devolvido"}
DO_QUE = {"produto e embalagem": "do produto e da embalagem",
          "personalização": "da personalização"}
ACAO = {"reenviar_produto": "o reenvio", "reimprimir_personalizacao": "a nova produção",
        "trocar_produto": "a troca", "reembolsar": "o reembolso"}
RETORNO = "Retornaremos por aqui assim que houver uma posição."


def _data(valor: date) -> str:
    return valor.strftime("%d/%m/%Y")


def _rs(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _do_pedido(pedido: dict | None) -> str:
    return f" do pedido {pedido['order_id']}" if pedido else ""


def pedir_numero_pedido() -> str:
    return ("Olá! Para localizarmos a sua compra, por favor nos informe o número do pedido "
            "(ele aparece no e-mail de confirmação da compra).")


def pedido_nao_localizado() -> str:
    return ("Olá! Não localizamos o pedido informado. Por favor, confira o número do pedido "
            "no e-mail de confirmação da compra e nos envie de novo.")


def em_analise(policy: Policy) -> str:
    regra = policy.regras["reclamacao_suspeita"]["comunicacao_com_cliente"]
    if "em análise" not in regra:  # o texto abaixo só vale enquanto a regra disser isso
        raise ValueError("politicas.csv mudou a comunicação de reclamação em análise")
    return f"Olá! Sua solicitação está em análise. {RETORNO}"


def _prazo(pedido: dict, policy: Policy, hoje: date) -> str:
    """Data prometida como previsão só se ainda não passou; vencida, é dita como prazo."""
    prometido = promised_date(pedido, policy)
    if prometido < hoje:
        return f"O prazo previsto era {_data(prometido)}."
    return f"A previsão de entrega é {_data(prometido)}."


def _status(pedido: dict, policy: Policy, hoje: date) -> str:
    status = pedido.get("status_entrega", "")
    texto = (f"Olá! Seu pedido {pedido['order_id']} está {STATUS.get(status, 'em andamento')}, "
             f"com a transportadora {pedido['transportadora']}.")
    if status == "entregue" and pedido.get("data_entrega"):
        return texto + f" A entrega consta em {_data(date.fromisoformat(pedido['data_entrega'][:10]))}."
    return f"{texto} {_prazo(pedido, policy, hoje)}"


def _chamado(pedido: dict, policy: Policy) -> str:
    return (f"Olá! Abrimos um chamado com a transportadora {pedido['transportadora']} sobre o "
            f"pedido {pedido['order_id']}, que tinha previsão de entrega para "
            f"{_data(promised_date(pedido, policy))}. Assim que tivermos o retorno, avisamos "
            "você por aqui.")


def _atraso(d: Decision) -> str:
    inicio = f"Olá! Pedimos desculpas pelo atraso do pedido {d.params['order_id']}. "
    if "reembolso" in d.params.get("opcoes", []):
        return (inicio + f"Você pode escolher entre o reenvio do produto sem custo ou o "
                f"reembolso de {_rs(d.params['valor'])}. Qual opção você prefere?")
    return (inicio + "Podemos reenviar o produto sem custo. Se preferir o reembolso, ele passa "
            "por aprovação interna. Responda por aqui como prefere seguir.")


def _por_ferramenta(d: Decision, pedido: dict | None, policy: Policy,
                    hoje: date) -> str | None:
    f, p = d.ferramenta, d.params
    if f == "informar_status":
        return _status(pedido, policy, hoje)
    if f == "abrir_chamado_transportadora":
        return _chamado(pedido, policy)
    if f == "solicitar_foto":
        do_que = DO_QUE.get(p.get("do_que", ""), "do produto")
        return (f"Olá! Para darmos andamento, por favor envie uma foto {do_que}"
                f"{_do_pedido(pedido)}.")
    if f == "negar_por_politica":
        return (f"Olá! Analisamos a sua solicitação{_do_pedido(pedido)} e, infelizmente, ela "
                f"está fora da nossa política. A regra é: \"{p['regra']}\"")
    if f == "solicitar_aprovacao":
        acao = ACAO.get(p.get("acao"), "a sua solicitação")
        return (f"Olá! Encaminhamos {acao}{_do_pedido(pedido)} para aprovação interna, pois o "
                f"valor passa do limite de aprovação do atendimento. {RETORNO}")
    if f == "reenviar_produto" and d.regra == "atraso_entrega":
        return _atraso(d)
    if f in ("reenviar_produto", "reimprimir_personalizacao"):
        return (f"Olá! Registramos {ACAO[f]} sem custo{_do_pedido(pedido)}. Avisaremos por "
                "aqui quando o envio sair.")
    if f == "trocar_produto":
        return (f"Olá! A troca do produto{_do_pedido(pedido)} está dentro da política. Para "
                "seguirmos, por favor nos diga qual produto você gostaria de receber.")
    if f == "reembolsar":
        return f"Olá! Registramos o reembolso de {_rs(p['valor'])}{_do_pedido(pedido)}."
    if f == "cancelar_pedido":
        return (f"Olá! Cancelamos o pedido {p['order_id']}, que ainda não tinha sido separado. "
                "O estorno é integral.")
    if f == "alterar_endereco":
        return (f"Olá! O pedido {p['order_id']} ainda não foi separado, então a alteração de "
                "endereço é possível. Nossa equipe vai registrar o novo endereço informado e "
                "confirmar com você por aqui.")
    if f == "verificar_pagamento":
        regra = policy.categorias["pagamento_pendente"]["regra"]
        return (f"Olá! Estamos verificando o pagamento{_do_pedido(pedido)}. "
                f"Pela nossa política: \"{regra}\"")
    if f == "validar_cupom":
        return ("Olá! Para verificarmos o cupom, por favor nos informe o código exatamente "
                "como ele aparece para você.")
    if f == "agradecer":
        return "Olá! Muito obrigado pela sua mensagem. Ficamos felizes com o seu retorno!"
    if f == "responder_cliente" and d.regra == "pedido_ausente":
        return pedir_numero_pedido()
    if f == "responder_cliente" and d.regra == "pedido_nao_localizado":
        return pedido_nao_localizado()
    if f == "acionar_pessoa":
        return f"Olá! Recebemos a sua mensagem e encaminhamos o caso para a equipe responsável. {RETORNO}"
    return None


def compor(d: Decision, pedido: dict | None, policy: Policy,
           now: datetime = NOW) -> str | None:
    """Texto para o cliente na decisão `d`, ou None quando nada é enviado pelo agente."""
    if d.regra == "reacao_adversa":
        return ("Olá! Por segurança, suspenda o uso do produto e, se necessário, procure "
                "atendimento médico. O seu relato foi encaminhado à equipe responsável, que vai "
                "acompanhar o caso com você.")
    return _por_ferramenta(d, pedido, policy, now.date())
