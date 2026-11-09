import csv
from dataclasses import replace
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pytest

from pipeline.config import NOW
from pipeline.data import load_dataset
from pipeline.decide import CONFIANCA_MINIMA, DIAS_UTEIS_RASTREIO_PARADO, Case, decide
from pipeline.models import Classificacao
from pipeline.policy import load_policy

from helpers import case_da_conversa, conversa_e_agora

POLICY = load_policy()
FINANCEIRAS = {"reenviar_produto", "reimprimir_personalizacao", "trocar_produto", "reembolsar"}
CASOS = Path(__file__).resolve().parent.parent / "evals" / "casos.csv"


def _pedido(**campos):
    """Pedido sintético entregue em 30/10 (3 dias antes de NOW); prometido para 03/11
    (28/10 + preparo Belleza 1 + TransLeste/SE 2 dias úteis; 02/11 é feriado)."""
    base = {"order_id": "GBHT00001", "customer_id": "CHT00001", "marca": "Lumen",
            "data_pedido": "2026-10-28", "valor": "150.00",
            "descricao_produto": "Body Mist Baunilha 200ml", "personalizacao": "",
            "transportadora": "TransLeste", "uf": "SP", "status_entrega": "entregue",
            "data_separacao": "2026-10-28 10:00:00", "data_entrega": "2026-10-30"}
    base.update(campos)
    return base


EM_TRANSITO = {"status_entrega": "em_transito", "data_entrega": ""}


def _anexo(**campos):
    base = {"anexo_id": "IMGT00001", "conversation_id": "ATT00001", "order_id": "GBHT00001",
            "customer_id": "CHT00001", "tipo": "foto_produto", "hash_perceptual": "00000000000000aa",
            "exif_data_captura": "", "exif_modelo_camera": "", "exif_software": "",
            "descricao_visual": "Body Mist Baunilha 200ml com o pote rachado."}
    base.update(campos)
    return base


FOTO_COERENTE = [_anexo()]
FOTO_SUSPEITA = [_anexo(exif_data_captura="2026-09-01 10:00:00")]


def _case(categoria, *, pedido=None, anexos=(), valor=150.0, now=NOW, confianca=0.9,
          sinais_risco=(), sem_movimento=None, secundaria=None, reenvios=(), itens=(),
          pagamentos=(), estornos=()):
    pedido = _pedido() if pedido is None else pedido
    cl = Classificacao(categoria=categoria, categoria_secundaria=secundaria,
                       order_id=(pedido or {}).get("order_id"), sinais_risco=list(sinais_risco),
                       confianca=confianca)
    anexos = list(anexos)
    return Case(classificacao=cl, pedido=pedido or None, cliente={"customer_id": "CHT00001"},
                anexos=anexos, todos_anexos=anexos, valor=valor, now=now,
                dias_uteis_sem_movimento=sem_movimento, reenvios_anteriores=list(reenvios),
                itens=list(itens), pagamentos=list(pagamentos), estornos=list(estornos))


def _d(*args, **kwargs):
    return decide(_case(*args, **kwargs), POLICY)


# --- 1. reação adversa / caso sensível ---

def test_reacao_adversa_devolve_as_duas_acoes_obrigatorias_via_pessoa():
    d = _d("reacao_adversa")
    assert d.ferramenta == "acionar_pessoa"
    assert d.params["acoes_obrigatorias"] == ["orientar_suspensao_uso", "registrar_cosmetovigilancia"]
    assert d.params["acoes_obrigatorias"] == POLICY.categorias["reacao_adversa"]["acoes_obrigatorias"]
    assert d.acao == "orientar_suspensao_uso;registrar_cosmetovigilancia"
    assert "24 h" in d.motivo


def test_reacao_adversa_vem_antes_da_suspeita():
    assert _d("reacao_adversa", anexos=FOTO_SUSPEITA).ferramenta == "acionar_pessoa"


def test_reacao_adversa_como_sinal_de_risco_em_outra_categoria():
    d = _d("avaria_vazamento", anexos=FOTO_COERENTE, sinais_risco=["reacao_adversa"])
    assert d.ferramenta == "acionar_pessoa" and "acoes_obrigatorias" in d.params


def test_ameaca_juridica_e_caso_sensivel():
    d = _d("avaria_vazamento", anexos=FOTO_COERENTE, sinais_risco=["ameaca_juridica"])
    assert d.ferramenta == "acionar_pessoa"


@pytest.mark.parametrize("categoria,anexos", [
    ("avaria_vazamento", FOTO_COERENTE), ("arrependimento_cancelamento", ()),
    ("cobranca_duplicada", ())])
def test_instrucao_no_texto_nao_executa_ferramenta_financeira(categoria, anexos):
    # verificação item 7: uma ordem no texto não pode virar reembolso/reenvio automático
    d = _d(categoria, anexos=anexos, valor=80.0, sinais_risco=["instrucao_no_texto"])
    assert d.ferramenta == "acionar_pessoa"
    assert d.params["area"] == "supervisao"
    assert "instrução" in d.motivo


def test_instrucao_no_texto_nao_cancela_com_estorno_sozinho():
    nao_separado = _pedido(data_separacao="", **EM_TRANSITO)
    assert _d("arrependimento_cancelamento", pedido=nao_separado).ferramenta == "cancelar_pedido"
    d = _d("arrependimento_cancelamento", pedido=nao_separado, sinais_risco=["instrucao_no_texto"])
    assert d.ferramenta == "acionar_pessoa"


def test_instrucao_no_texto_mantem_ferramenta_nao_financeira():
    # M01: atraso legítimo com instrução escondida segue com o chamado na transportadora
    d = _d("onde_esta_pedido", pedido=_pedido(**EM_TRANSITO), sem_movimento=5,
           sinais_risco=["instrucao_no_texto"])
    assert d.ferramenta == "abrir_chamado_transportadora"


def test_sinal_fraco_nao_afirma_foto_coerente():
    # verificação item 2
    d = _d("avaria_vazamento", anexos=FOTO_GENERICA, valor=150.0)
    assert "Foto coerente" not in d.motivo
    assert "sinal fraco" in d.motivo


def test_confianca_baixa_vai_para_pessoa():
    assert CONFIANCA_MINIMA == 0.6
    assert _d("elogio", confianca=0.59).ferramenta == "acionar_pessoa"
    assert _d("elogio", confianca=0.6).ferramenta == "agradecer"


# --- 2. reclamação sinalizada ---

def test_com_sinais_sinaliza_e_nenhuma_acao_financeira():
    d = _d("avaria_vazamento", anexos=FOTO_SUSPEITA)
    assert d.acao == d.ferramenta == "sinalizar_suspeita"
    assert d.ferramenta not in FINANCEIRAS
    assert [s.kind for s in d.evidencias] == ["exif_fora_da_janela"]
    assert d.params["sinais"] == ["exif_fora_da_janela"]
    assert "em análise" in d.motivo


FOTO_GENERICA = [_anexo(descricao_visual="Frasco quebrado com liquido vazado na caixa.")]
FOTO_EDITADA = [_anexo(exif_data_captura="2026-10-31 10:00:00",
                       exif_software="Editor de Fotos do Galaxy")]


def test_descricao_generica_honesta_nao_sinaliza():
    # R6b: sinal fraco sozinho segue o fluxo normal e fica só como evidência informativa
    d = _d("avaria_vazamento", anexos=FOTO_GENERICA, valor=150.0)
    assert d.ferramenta == "reenviar_produto"
    assert [s.kind for s in d.evidencias] == ["descricao_incoerente"]


def test_software_de_edicao_sozinho_nao_sinaliza():
    d = _d("avaria_vazamento", anexos=FOTO_EDITADA, valor=150.0)
    assert d.ferramenta == "reenviar_produto"
    assert [s.kind for s in d.evidencias] == ["exif_software_edicao"]


def test_sinal_forte_com_fracos_sinaliza_listando_todos():
    anexos = [_anexo(exif_data_captura="2026-09-01 10:00:00",
                     exif_software="Editor de Fotos do Galaxy",
                     descricao_visual="Frasco quebrado com liquido vazado na caixa.")]
    d = _d("avaria_vazamento", anexos=anexos)
    assert d.ferramenta == "sinalizar_suspeita"
    kinds = {"exif_fora_da_janela", "exif_software_edicao", "descricao_incoerente"}
    assert {s.kind for s in d.evidencias} == kinds
    assert set(d.params["sinais"]) == kinds


def test_sinais_suspendem_tambem_o_reembolso():
    d = _d("cobranca_duplicada", anexos=FOTO_SUSPEITA, valor=50.0)
    assert d.ferramenta == "sinalizar_suspeita"


def test_suspeita_vem_antes_do_prazo_e_da_alcada():
    entregue_ha_9 = _pedido(data_entrega="2026-10-24")
    assert _d("avaria_vazamento", pedido=entregue_ha_9, anexos=FOTO_SUSPEITA,
              valor=250.0).ferramenta == "sinalizar_suspeita"


# --- 3. sem foto ---

@pytest.mark.parametrize("categoria", ["avaria_vazamento", "item_faltante", "erro_personalizacao"])
def test_sem_anexos_solicita_foto(categoria):
    d = _d(categoria)
    assert d.ferramenta == "solicitar_foto"


@pytest.mark.parametrize("categoria", ["avaria_vazamento", "item_faltante"])
def test_prazo_vem_antes_da_foto(categoria):
    # R6d: recebido há 12 dias e sem foto -> explica a política em vez de pedir foto
    d = _d(categoria, pedido=_pedido(data_entrega="2026-10-21"))
    assert d.ferramenta == "negar_por_politica"


@pytest.mark.parametrize("categoria", ["avaria_vazamento", "item_faltante"])
def test_dentro_do_prazo_sem_foto_pede_foto(categoria):
    assert _d(categoria, pedido=_pedido(data_entrega="2026-10-30")).ferramenta == "solicitar_foto"


# --- 4. fora do prazo ---

def test_entregue_ha_9_dias_nega_por_politica():
    d = _d("avaria_vazamento", pedido=_pedido(data_entrega="2026-10-24"), anexos=FOTO_COERENTE)
    assert d.ferramenta == "negar_por_politica"


def test_entregue_ha_exatamente_7_dias_ainda_esta_no_prazo():
    d = _d("avaria_vazamento", pedido=_pedido(data_entrega="2026-10-26"), anexos=FOTO_COERENTE)
    assert d.ferramenta == "reenviar_produto"


def test_prazo_vem_da_policy():
    pol = replace(POLICY, prazo_dias=10)
    case = _case("avaria_vazamento", pedido=_pedido(data_entrega="2026-10-24"), anexos=FOTO_COERENTE)
    assert decide(case, pol).ferramenta == "reenviar_produto"


# --- 5. alçada ---

def test_avaria_coerente_entregue_ha_3_dias_r150_reenvia():
    d = _d("avaria_vazamento", anexos=FOTO_COERENTE, valor=150.0)
    assert d.acao == d.ferramenta == "reenviar_produto"
    assert d.params["valor"] == 150.0 and d.params["order_id"] == "GBHT00001"


def test_mesmo_caso_r250_pede_aprovacao():
    d = _d("avaria_vazamento", anexos=FOTO_COERENTE, valor=250.0)
    assert d.ferramenta == "solicitar_aprovacao"
    assert d.params["acao"] == "reenviar_produto" and d.params["valor"] == 250.0


def test_valor_igual_ao_limite_esta_na_alcada():
    # "até R$ 200" / "acima de R$ 100 exige aprovação": o limite é inclusivo
    assert _d("avaria_vazamento", anexos=FOTO_COERENTE,
              valor=POLICY.limite_reenvio).ferramenta == "reenviar_produto"
    assert _d("cobranca_duplicada", valor=POLICY.limite_reembolso).ferramenta == "reembolsar"


def test_limite_vem_da_policy():
    case = _case("avaria_vazamento", anexos=FOTO_COERENTE, valor=150.0)
    assert decide(case, replace(POLICY, limite_reenvio=100.0)).ferramenta == "solicitar_aprovacao"


def test_erro_personalizacao_reimprime():
    d = _d("erro_personalizacao", anexos=FOTO_COERENTE, valor=150.0)
    assert d.ferramenta == "reimprimir_personalizacao"


def test_reembolso_r120_pede_aprovacao_e_r90_reembolsa():
    assert _d("cobranca_duplicada", valor=120.0).ferramenta == "solicitar_aprovacao"
    assert _d("cobranca_duplicada", valor=90.0).ferramenta == "reembolsar"


# --- pedido ainda não entregue (regra 2) ---

@pytest.mark.parametrize("categoria", ["avaria_vazamento", "item_faltante", "erro_personalizacao"])
@pytest.mark.parametrize("now,esperado", [
    (datetime(2026, 11, 2, 8), "informar_status"),        # antes de 03/11 (prometido)
    (datetime(2026, 11, 6, 8), "abrir_chamado_transportadora"),
    (datetime(2026, 11, 30, 8), "abrir_chamado_transportadora"),
])
def test_reclamacao_fisica_sem_entrega_nunca_reenvia(categoria, now, esperado):
    d = _d(categoria, pedido=_pedido(**EM_TRANSITO), anexos=FOTO_COERENTE, now=now)
    assert d.ferramenta == esperado


def test_avaria_extraviado_nao_reenvia():
    pedido = _pedido(status_entrega="extraviado", data_entrega="")
    assert _d("avaria_vazamento", pedido=pedido, anexos=FOTO_COERENTE).ferramenta != "reenviar_produto"


# R6a: ação exata para cada status_entrega diferente de "entregue" que existe em pedidos.csv.
# devolvido traz data_entrega nos dados (40 pedidos); os demais vêm sem data.
POR_STATUS = {
    "aguardando_separacao": ({"data_entrega": ""}, "informar_status"),  # NOW <= prometido 03/11
    "em_transito": ({"data_entrega": ""}, "informar_status"),
    "extraviado": ({"data_entrega": ""}, "abrir_chamado_transportadora"),
    "cancelado": ({"data_entrega": ""}, "acionar_pessoa"),
    "devolvido": ({}, "acionar_pessoa"),  # mantém data_entrega 30/10 do pedido base
}


def test_por_status_cobre_todos_os_status_nao_entregues_dos_dados():
    status = {p["status_entrega"] for p in _ds().pedidos.values()} - {"entregue"}
    assert status == set(POR_STATUS)


@pytest.mark.parametrize("categoria", ["avaria_vazamento", "item_faltante", "erro_personalizacao"])
@pytest.mark.parametrize("status", sorted(POR_STATUS))
def test_reclamacao_fisica_por_status_nao_entregue(categoria, status):
    campos, esperado = POR_STATUS[status]
    pedido = _pedido(status_entrega=status, **campos)
    d = _d(categoria, pedido=pedido, anexos=FOTO_COERENTE, valor=50.0)
    assert d.ferramenta == esperado
    if esperado == "acionar_pessoa":
        assert d.params["area"] == "logistica"


@pytest.mark.parametrize("status", ["devolvido", "cancelado"])
def test_atraso_em_pedido_devolvido_ou_cancelado_vai_para_pessoa(status):
    campos = POR_STATUS[status][0]
    pedido = _pedido(status_entrega=status, **campos)
    d = _d("atraso_entrega", pedido=pedido, now=datetime(2026, 11, 30, 8), valor=50.0)
    assert d.ferramenta == "acionar_pessoa" and d.params["area"] == "logistica"


def test_arrependimento_em_pedido_devolvido_continua_pela_data_de_entrega():
    # N06: devolvido com data_entrega; arrependimento usa só a data
    pedido = _pedido(status_entrega="devolvido")
    assert _d("arrependimento_cancelamento", pedido=pedido, valor=90.0).ferramenta == "reembolsar"


def test_atraso_dentro_do_prazo_informa_status():
    assert _d("atraso_entrega", pedido=_pedido(**EM_TRANSITO)).ferramenta == "informar_status"


def test_atraso_ate_limite_abre_chamado():
    # prometido 03/11; 12/11 = 7 dias úteis depois (feriado 20/11 fora da janela)
    d = _d("atraso_entrega", pedido=_pedido(**EM_TRANSITO), now=datetime(2026, 11, 12, 8))
    assert d.ferramenta == "abrir_chamado_transportadora"


def _atraso_acima_do_limite(valor, policy=POLICY):
    case = _case("atraso_entrega", pedido=_pedido(**EM_TRANSITO), now=datetime(2026, 11, 13, 8),
                 valor=valor)
    return decide(case, policy)


def test_atraso_acima_do_limite_reembolso_so_e_opcao_dentro_da_alcada_de_reembolso():
    # R6c: limite_reembolso = 100, limite_reenvio = 200 (politicas.csv)
    d = _atraso_acima_do_limite(100.00)
    assert d.ferramenta == "reenviar_produto"
    assert d.params["opcoes"] == ["reenvio", "reembolso"]
    assert "reembolso_exige_aprovacao" not in d.params


def test_atraso_acima_do_limite_reembolso_acima_da_alcada_nao_e_oferecido():
    d = _atraso_acima_do_limite(100.01)
    assert d.ferramenta == "reenviar_produto"
    assert d.params["opcoes"] == ["reenvio"]
    assert d.params["reembolso_exige_aprovacao"] is True


def test_atraso_acima_do_limite_e_acima_da_alcada_pede_aprovacao():
    d = _atraso_acima_do_limite(200.01)
    assert d.ferramenta == "solicitar_aprovacao"
    assert d.params["acao"] == "reenviar_produto" and d.params["opcoes"] == ["reenvio"]


def test_opcao_de_reembolso_usa_o_limite_da_policy():
    d = _atraso_acima_do_limite(150.0, replace(POLICY, limite_reembolso=150.0))
    assert d.params["opcoes"] == ["reenvio", "reembolso"]


def test_atraso_extraviado_reenvia():
    pedido = _pedido(status_entrega="extraviado", data_entrega="")
    assert _d("atraso_entrega", pedido=pedido).ferramenta == "reenviar_produto"


def test_entrega_futura_em_relacao_ao_agora_conta_como_nao_entregue():
    # histórico: o pedido traz a foto final; na hora da conversa ainda não tinha chegado
    pedido = _pedido(data_entrega="2026-11-05")
    assert _d("atraso_entrega", pedido=pedido).ferramenta == "informar_status"


# --- regra 1: onde está o pedido ---

@pytest.mark.parametrize("sem_movimento,esperado", [
    (None, "informar_status"), (2, "informar_status"), (3, "abrir_chamado_transportadora")])
def test_onde_esta_pedido(sem_movimento, esperado):
    d = _d("onde_esta_pedido", pedido=_pedido(**EM_TRANSITO), sem_movimento=sem_movimento)
    assert d.ferramenta == esperado


def test_dias_de_rastreio_parado_conferem_com_o_texto_da_politica():
    regra = POLICY.categorias["onde_esta_pedido"]["regra"]
    assert f"{DIAS_UTEIS_RASTREIO_PARADO} dias úteis ou mais" in regra


# --- regra 5: demais categorias ---

def test_arrependimento():
    antes = _pedido(status_entrega="aguardando_separacao", data_separacao="", data_entrega="")
    assert _d("arrependimento_cancelamento", pedido=antes).ferramenta == "cancelar_pedido"
    assert _d("arrependimento_cancelamento", valor=90.0).ferramenta == "reembolsar"
    assert _d("arrependimento_cancelamento", valor=150.0).ferramenta == "solicitar_aprovacao"
    tarde = _pedido(data_entrega="2026-10-20")
    assert _d("arrependimento_cancelamento", pedido=tarde, valor=90.0).ferramenta == "negar_por_politica"


def test_alteracao_endereco():
    antes = _pedido(status_entrega="aguardando_separacao", data_separacao="", data_entrega="")
    assert _d("alteracao_endereco", pedido=antes).ferramenta == "alterar_endereco"
    separa_depois = _pedido(data_separacao="2026-11-03 10:00:00", **EM_TRANSITO)
    assert _d("alteracao_endereco", pedido=separa_depois).ferramenta == "alterar_endereco"
    assert _d("alteracao_endereco", pedido=_pedido(**EM_TRANSITO)).ferramenta == "negar_por_politica"


def test_troca_fragrancia():
    ha_20_dias = _pedido(data_entrega="2026-10-13")
    assert _d("troca_fragrancia", pedido=ha_20_dias, valor=150.0).ferramenta == "trocar_produto"
    assert _d("troca_fragrancia", pedido=ha_20_dias, valor=250.0).ferramenta == "solicitar_aprovacao"
    ha_31_dias = _pedido(data_entrega="2026-10-02")
    assert _d("troca_fragrancia", pedido=ha_31_dias).ferramenta == "negar_por_politica"


@pytest.mark.parametrize("categoria,ferramenta", [
    ("pagamento_pendente", "verificar_pagamento"), ("duvida_produto", "responder_duvida"),
    ("cupom_promocao", "validar_cupom"), ("elogio", "agradecer"),
    ("sem_interacao", "encerrar_conversa")])
def test_categorias_simples(categoria, ferramenta):
    assert _d(categoria).ferramenta == ferramenta


def test_reclamacao_sem_pedido_vai_para_pessoa():
    assert _d("avaria_vazamento", pedido={}, anexos=FOTO_COERENTE).ferramenta == "acionar_pessoa"


def test_categoria_desconhecida_vai_para_pessoa():
    assert _d("outra_coisa").ferramenta == "acionar_pessoa"


# --- contexto do pedido: reenvio anterior sem o brinde (D04) ---

def _item(sku, tipo="venda", preco="150.00"):
    return {"order_id": "GBHT00001", "sku": sku, "tipo_item": tipo, "preco_unitario": preco}


def _reenvio(sku, solicitacao_id="OMST0001", tipo="reenvio"):
    return {"solicitacao_id": solicitacao_id, "order_id_original": "GBHT00001", "tipo": tipo,
            "sku_enviado": sku, "data_solicitacao": "2026-10-31 10:00:00"}


ITENS_COM_BRINDE = [_item("KSH-T1"), _item("GBT-T9", tipo="brinde", preco="0.00")]
ENTREGUE_HA_12 = {"data_entrega": "2026-10-21"}


@pytest.mark.parametrize("categoria", ["avaria_vazamento", "item_faltante", "erro_personalizacao"])
@pytest.mark.parametrize("anexos", [[], FOTO_COERENTE])
@pytest.mark.parametrize("entrega", [{}, ENTREGUE_HA_12])
def test_reenvio_anterior_sem_o_brinde_vai_para_pessoa(categoria, anexos, entrega):
    # nunca pede foto de novo nem nega por prazo: o reenvio anterior não levou o brinde
    d = _d(categoria, pedido=_pedido(**entrega), anexos=anexos, itens=ITENS_COM_BRINDE,
           reenvios=[_reenvio("KSH-T1")])
    assert d.acao == d.ferramenta == "acionar_pessoa"
    assert d.params["area"] == "qualidade"
    assert d.params["reenvio_anterior"] == "OMST0001"
    assert d.params["sku_nao_coberto"] == "GBT-T9"
    assert d.regra == categoria


def test_brinde_por_preco_zero_sem_tipo_brinde():
    itens = [_item("KSH-T1"), _item("GBT-T9", preco="0.00")]
    d = _d("item_faltante", itens=itens, reenvios=[_reenvio("KSH-T1")])
    assert d.ferramenta == "acionar_pessoa" and d.params["sku_nao_coberto"] == "GBT-T9"


def test_reenvio_que_ja_levou_o_brinde_segue_a_regra_normal():
    d = _d("item_faltante", itens=ITENS_COM_BRINDE, reenvios=[_reenvio("GBT-T9")])
    assert d.ferramenta == "solicitar_foto"


def test_sem_reenvio_anterior_segue_a_regra_normal():
    assert _d("item_faltante", itens=ITENS_COM_BRINDE).ferramenta == "solicitar_foto"


def test_troca_anterior_nao_conta_como_reenvio():
    d = _d("item_faltante", itens=ITENS_COM_BRINDE, reenvios=[_reenvio("KSH-T1", tipo="troca")])
    assert d.ferramenta == "solicitar_foto"


def test_reenvio_sem_brinde_nao_muda_outras_categorias():
    d = _d("arrependimento_cancelamento", valor=90.0, itens=ITENS_COM_BRINDE,
           reenvios=[_reenvio("KSH-T1")])
    assert d.ferramenta == "reembolsar"


def test_suspeita_vem_antes_do_reenvio_sem_brinde():
    d = _d("item_faltante", anexos=FOTO_SUSPEITA, itens=ITENS_COM_BRINDE,
           reenvios=[_reenvio("KSH-T1")])
    assert d.ferramenta == "sinalizar_suspeita"


def test_anexo_de_outra_conversa_do_pedido_satisfaz_a_foto():
    # Case.anexos é do PEDIDO: foto enviada em outra conversa do mesmo pedido já basta
    outra = [_anexo(conversation_id="ATOUTRA1")]
    assert _d("item_faltante", anexos=outra).ferramenta == "reenviar_produto"


# --- contexto do pedido: cobrança duplicada em aberto no arrependimento (N06) ---

def _trx(tid, status="capturada", valor="90.00", criacao="2026-10-28 09:00:00"):
    return {"transacao_id": tid, "order_id": "GBHT00001", "valor": valor, "status": status,
            "data_hora_criacao": criacao, "data_hora_confirmacao": criacao}


def _estorno(tid, processamento="2026-11-01 10:00:00", status="concluido"):
    return {"estorno_id": "ESTT0001", "transacao_id": tid, "order_id": "GBHT00001",
            "valor": "90.00", "status": status, "data_hora_solicitacao": "2026-10-31 10:00:00",
            "data_hora_processamento": processamento}


DUPLICADA = [_trx("TRXT1"), _trx("TRXT2", status="estornada", criacao="2026-10-28 09:01:00")]


def test_arrependimento_com_duplicidade_em_aberto_vai_para_pessoa():
    d = _d("arrependimento_cancelamento", valor=90.0, pagamentos=DUPLICADA)
    assert d.acao == d.ferramenta == "acionar_pessoa"
    assert d.regra == "arrependimento_cancelamento"
    assert d.params["categoria_secundaria"] == "cobranca_duplicada"
    assert d.params["transacoes"] == ["TRXT1", "TRXT2"]
    assert d.params["valores_reembolso"] == [90.0, 90.0]
    assert d.params["total_reembolso"] == 180.0
    assert d.params["limite_reembolso"] == POLICY.limite_reembolso
    assert "por ação ou pela soma" in d.motivo


def test_duplicidade_em_aberto_dentro_do_limite_tambem_vai_para_pessoa():
    # dois reembolsos de naturezas diferentes; a política não trata a combinação
    pagamentos = [_trx("TRXT1", valor="40.00"), _trx("TRXT2", valor="40.00")]
    d = _d("arrependimento_cancelamento", valor=40.0, pagamentos=pagamentos)
    assert d.ferramenta == "acionar_pessoa" and d.params["total_reembolso"] == 80.0
    assert "dentro do limite" in d.motivo


def test_estorno_pedido_mas_nao_processado_mantem_a_duplicidade_em_aberto():
    for estorno in (_estorno("TRXT2", processamento="2026-11-03 10:00:00"),
                    _estorno("TRXT2", processamento="", status="em_processamento")):
        d = _d("arrependimento_cancelamento", valor=90.0, pagamentos=DUPLICADA,
               estornos=[estorno])
        assert d.ferramenta == "acionar_pessoa"


@pytest.mark.parametrize("pagamentos,estornos", [
    ([], []),
    ([_trx("TRXT1")], []),
    (DUPLICADA, [_estorno("TRXT2")]),  # estorno processado antes de agora: não há duplicidade
    ([_trx("TRXT1"), _trx("TRXT2", status="recusada")], []),
])
def test_sem_duplicidade_em_aberto_o_arrependimento_nao_muda(pagamentos, estornos):
    d = _d("arrependimento_cancelamento", valor=90.0, pagamentos=pagamentos, estornos=estornos)
    assert d.ferramenta == "reembolsar"


def test_cobranca_duplicada_mantem_a_regra_propria():
    assert _d("cobranca_duplicada", valor=90.0, pagamentos=DUPLICADA).ferramenta == "reembolsar"


def test_decisoes_de_contexto_nao_acusam():
    for d in (_d("item_faltante", itens=ITENS_COM_BRINDE, reenvios=[_reenvio("KSH-T1")]),
              _d("arrependimento_cancelamento", pagamentos=DUPLICADA)):
        texto = " ".join([d.motivo, str(d.params)]).lower()
        assert "fraude" not in texto and "golpe" not in texto


# --- nunca acusar ---

@pytest.mark.parametrize("categoria", list(POLICY.categorias) + ["outra_coisa"])
@pytest.mark.parametrize("anexos", [[], FOTO_COERENTE, FOTO_SUSPEITA])
@pytest.mark.parametrize("pedido", [_pedido(), _pedido(**EM_TRANSITO), _pedido(data_entrega="2026-10-01")])
def test_nenhuma_decisao_acusa(categoria, anexos, pedido):
    d = _d(categoria, pedido=pedido, anexos=anexos)
    texto = " ".join([d.motivo, d.regra, str(d.params)] + [s.detail for s in d.evidencias]).lower()
    assert "fraude" not in texto and "golpe" not in texto


# --- casos de avaliação com dados reais (sem modelo) ---

@lru_cache(maxsize=1)
def _ds():
    return load_dataset()


def _casos():
    with open(CASOS, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _case_real(caso, confianca=0.9, sinais_risco=()):
    """Case da conversa real como estava em `now` (tests/helpers.py, reutilizável na Task 7)."""
    ds = _ds()
    conv, _ = conversa_e_agora(ds, caso["conversation_id"])
    cl = Classificacao(categoria=caso["categoria_esperada"], categoria_secundaria=None,
                       order_id=conv["order_id"], sinais_risco=list(sinais_risco),
                       confianca=confianca)
    return case_da_conversa(ds, caso["conversation_id"], cl)


DERIVAVEIS = ["N01", "N02", "N03", "N04", "N05", "N06", "N07", "N08",
              "D01", "D02", "D03", "D04", "M01"]


@pytest.mark.parametrize("caso_id", DERIVAVEIS)
def test_caso_real_bate_com_a_acao_esperada(caso_id):
    caso = next(c for c in _casos() if c["caso_id"] == caso_id)
    d = decide(_case_real(caso), POLICY)
    assert d.acao == caso["acao_esperada"]
    assert d.regra == caso["regra_politicas"]


def test_d01_real_sinaliza_pela_data_de_captura_sem_olhar_o_futuro():
    # R6e: em 06/08 (abertura do D01) a mesma imagem ainda não tinha sido enviada em outra
    # conversa (IMG000098 é de 31/08); o sinal forte é a captura anterior ao pedido.
    caso = next(c for c in _casos() if c["caso_id"] == "D01")
    d = decide(_case_real(caso), POLICY)
    kinds = {s.kind for s in d.evidencias}
    assert d.ferramenta == "sinalizar_suspeita"
    assert "exif_fora_da_janela" in kinds
    assert "hash_repetido" not in kinds


# Ambiguidade como SINAL do classificador (decisão do controller, Task 8): o modelo é
# confiante demais (A01/A02 saíram com confiança 0,97-0,99), então a confiança não separa o
# ambíguo. O modelo só marca o sinal; a ação é decidida aqui no código.
AMBIGUOS = {"A01": "duvida_elegibilidade_cupom", "A02": "sem_politica_aplicavel"}


@pytest.mark.parametrize("caso_id", ["A01", "A02"])
def test_ambiguos_pelo_sinal_de_risco_batem_com_a_acao_esperada(caso_id):
    caso = next(c for c in _casos() if c["caso_id"] == caso_id)
    d = decide(_case_real(caso, sinais_risco=[AMBIGUOS[caso_id]]), POLICY)
    assert d.acao == caso["acao_esperada"]
    assert d.regra == caso["regra_politicas"]
    assert d.ferramenta == "acionar_pessoa"


def test_cupom_sem_politica_aplicavel_vai_para_pessoa_sem_validar():
    d = _d("cupom_promocao", pedido={}, sinais_risco=["sem_politica_aplicavel"])
    assert (d.acao, d.ferramenta, d.regra) == ("acionar_pessoa", "acionar_pessoa", "cupom_promocao")
    assert "acoes_previas" not in d.params


def test_cupom_com_duvida_de_elegibilidade_valida_antes_de_acionar_pessoa():
    d = _d("cupom_promocao", pedido={}, sinais_risco=["duvida_elegibilidade_cupom"])
    assert d.ferramenta == "acionar_pessoa"
    assert d.params["acoes_previas"] == ["validar_cupom"]
    assert d.acao == "validar_cupom;acionar_pessoa"


def test_sem_politica_tem_precedencia_sobre_duvida_de_elegibilidade():
    d = _d("cupom_promocao", pedido={},
           sinais_risco=["duvida_elegibilidade_cupom", "sem_politica_aplicavel"])
    assert d.acao == "acionar_pessoa" and "acoes_previas" not in d.params


def test_cupom_sem_sinal_segue_validar_cupom():
    assert _d("cupom_promocao", pedido={}).ferramenta == "validar_cupom"


def test_sinais_de_cupom_nao_mudam_outras_categorias():
    d = _d("onde_esta_pedido", pedido=_pedido(**EM_TRANSITO),
           sinais_risco=["sem_politica_aplicavel"])
    assert d.ferramenta == "informar_status"


def test_d04_real_brinde_fora_do_reenvio_vai_para_pessoa_sem_foto_nem_prazo():
    caso = next(c for c in _casos() if c["caso_id"] == "D04")
    d = decide(_case_real(caso), POLICY)
    assert d.ferramenta == "acionar_pessoa"
    assert d.params["reenvio_anterior"] == "OMS000613"
    assert d.params["sku_nao_coberto"] == "GBT-9001"


def test_n06_real_duplicidade_em_aberto_vai_para_pessoa():
    caso = next(c for c in _casos() if c["caso_id"] == "N06")
    d = decide(_case_real(caso), POLICY)
    assert d.ferramenta == "acionar_pessoa"
    assert d.params["categoria_secundaria"] == "cobranca_duplicada"
    assert d.params["valores_reembolso"] == [99.66, 99.66]
    assert d.params["total_reembolso"] == 199.32
