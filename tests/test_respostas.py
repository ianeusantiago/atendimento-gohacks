import re
from functools import lru_cache

import pytest

from pipeline import respostas
from pipeline.case_builder import build_case
from pipeline.config import NOW
from pipeline.data import load_dataset
from pipeline.deadlines import promised_date
from pipeline.decide import Decision, decide
from pipeline.evidence import Signal
from pipeline.gateway import CsvGateway
from pipeline.mask import contains_pii
from pipeline.models import Classificacao
from pipeline.policy import load_policy

POLICY = load_policy()
PROIBIDAS = re.compile(r"fraud|golpe|suspeit|mentir|falsifica", re.IGNORECASE)


@lru_cache(maxsize=1)
def _gw():
    return CsvGateway(load_dataset())


def _pedido(**campos):
    base = {"order_id": "GBHT00001", "customer_id": "CHT00001", "marca": "Lumen",
            "data_pedido": "2026-10-28", "valor": "150.00",
            "descricao_produto": "Body Mist Baunilha 200ml", "personalizacao": "",
            "transportadora": "TransLeste", "uf": "SP", "status_entrega": "em_transito",
            "data_separacao": "2026-10-28 10:00:00", "data_entrega": ""}
    base.update(campos)
    return base


def _dec(ferramenta, regra_politica="onde_esta_pedido", /, acao=None, **params):
    return Decision(acao or ferramenta, ferramenta, params, "motivo", regra_politica, [])


def _todas_as_decisoes_reais():
    """Cada conversa da fila decidida com cada categoria de politicas.csv (sem modelo)."""
    gw = _gw()
    for conv in gw.fila():
        for categoria in POLICY.categorias:
            cl = Classificacao(categoria, None, conv["order_id"] or None, [], 0.9)
            case = build_case(gw, conv["conversation_id"], NOW, cl, conv["order_id"], POLICY)
            yield decide(case, POLICY), case.pedido


def test_nenhum_template_tem_pii_nem_palavra_acusatoria():
    textos = [respostas.compor(d, p, POLICY) for d, p in _todas_as_decisoes_reais()]
    textos += [respostas.em_analise(POLICY), respostas.pedir_numero_pedido(),
               respostas.pedido_nao_localizado()]
    escritos = [t for t in textos if t]
    assert len(escritos) > 500
    for t in escritos:
        assert not contains_pii(t), t
        assert not PROIBIDAS.search(t), t


def test_informar_status_traz_status_transportadora_e_previsao():
    pedido = _pedido()
    texto = respostas.compor(_dec("informar_status", order_id="GBHT00001"), pedido, POLICY)
    assert "GBHT00001" in texto and "TransLeste" in texto and "em trânsito" in texto
    assert promised_date(pedido, POLICY).strftime("%d/%m/%Y") in texto


def test_negar_por_politica_cita_a_regra_de_politicas_csv():
    regra = POLICY.categorias["alteracao_endereco"]["regra"]
    d = _dec("negar_por_politica", "alteracao_endereco", regra=regra)
    assert regra in respostas.compor(d, _pedido(), POLICY)


def test_sinalizar_suspeita_nao_envia_nada_ao_cliente():
    sinal = Signal("hash_repetido", "IMG1: mesma imagem")
    d = Decision("sinalizar_suspeita", "sinalizar_suspeita", {}, "m", "reclamacao_suspeita",
                 [sinal])
    assert respostas.compor(d, _pedido(), POLICY) is None


def test_em_analise_segue_a_regra_de_comunicacao_de_politicas_csv():
    regra = POLICY.regras["reclamacao_suspeita"]["comunicacao_com_cliente"]
    assert "solicitação está em análise" in regra
    assert "solicitação está em análise" in respostas.em_analise(POLICY)


def test_pagamento_pendente_cita_o_prazo_da_politica():
    regra = POLICY.categorias["pagamento_pendente"]["regra"]
    d = _dec("verificar_pagamento", "pagamento_pendente", order_id="GBHT00001")
    assert regra in respostas.compor(d, _pedido(), POLICY)


@pytest.mark.parametrize("decisao,trecho", [
    (_dec("solicitar_foto", "avaria_vazamento", do_que="produto e embalagem"),
     "foto do produto e da embalagem"),
    (_dec("solicitar_aprovacao", "cobranca_duplicada", acao="solicitar_aprovacao",
          order_id="GBHT00001", valor=150.0), "aprovação"),
    (_dec("acionar_pessoa", "reacao_adversa", acao="orientar_suspensao_uso;"
          "registrar_cosmetovigilancia", area="supervisao"), "suspenda o uso"),
    (_dec("reenviar_produto", "atraso_entrega", order_id="GBHT00001", valor=150.0,
          opcoes=["reenvio", "reembolso"]), "reembolso de R$ 150,00"),
    (_dec("acionar_pessoa", "pedido_ausente", area="supervisao"), "equipe"),
])
def test_textos_concretos_por_decisao(decisao, trecho):
    assert trecho in respostas.compor(decisao, _pedido(), POLICY)


def test_encerrar_e_responder_duvida_nao_tem_texto_do_agente():
    assert respostas.compor(_dec("encerrar_conversa", "sem_interacao"), None, POLICY) is None


def test_prazo_vencido_nao_e_chamado_de_previsao():
    pedido = _pedido(data_pedido="2026-10-20")  # prometido antes de 02/11
    prometido = promised_date(pedido, POLICY)
    assert prometido < NOW.date()
    texto = respostas.compor(_dec("informar_status", order_id="GBHT00001"), pedido, POLICY,
                             now=NOW)
    assert "previsão" not in texto
    assert f"prazo previsto era {prometido.strftime('%d/%m/%Y')}" in texto


def test_atraso_com_uma_so_opcao_nao_fala_em_escolher_entre():
    d = _dec("reenviar_produto", "atraso_entrega", order_id="GBHT00001", valor=150.0,
             opcoes=["reenvio"], reembolso_exige_aprovacao=True)
    texto = respostas.compor(d, _pedido(), POLICY)
    assert "escolher entre" not in texto
    assert "reenviar o produto sem custo" in texto and "aprovação interna" in texto
