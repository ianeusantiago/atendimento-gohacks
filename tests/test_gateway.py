from datetime import datetime
from functools import lru_cache

import pytest

from pipeline.asof import pedido_as_of
from pipeline.case_builder import build_case, conversa_e_agora
from pipeline.config import NOW
from pipeline.data import load_dataset
from pipeline.gateway import CsvGateway, Gateway
from pipeline.models import Classificacao
from pipeline.policy import load_policy

POLICY = load_policy()


@lru_cache(maxsize=1)
def _ds():
    return load_dataset()


def _gw():
    return CsvGateway(_ds(), toolbox=None)


def _cl(categoria="onde_esta_pedido", order_id=None):
    return Classificacao(categoria=categoria, categoria_secundaria=None, order_id=order_id,
                         confianca=0.9)


def test_csv_gateway_satisfaz_o_protocolo():
    assert isinstance(_gw(), Gateway)


def test_conversa_da_fila_e_do_historico():
    gw = _gw()
    assert gw.get_conversa("CV000033")["order_id"]  # fila (N01)
    assert gw.get_conversa("CV000001")["customer_id"]  # histórico (D01)
    assert gw.get_conversa("NAO_EXISTE") is None


def test_pedido_cliente_e_anexos_de_uma_conversa_conhecida():
    gw = _gw()
    conv = gw.get_conversa("CV000001")
    pedido = gw.get_pedido(conv["order_id"])
    assert pedido["customer_id"] == conv["customer_id"]
    assert gw.get_cliente(conv["customer_id"])["customer_id"] == conv["customer_id"]
    anexos = gw.get_anexos(conversation_id="CV000001")
    assert anexos and all(a["conversation_id"] == "CV000001" for a in anexos)
    por_pedido = gw.get_anexos(order_id=conv["order_id"])
    assert por_pedido and all(a["order_id"] == conv["order_id"] for a in por_pedido)


def test_ids_inexistentes_devolvem_none_ou_vazio():
    gw = _gw()
    assert gw.get_pedido("GXH000000") is None
    assert gw.get_cliente("CX000000") is None
    assert gw.get_anexos(conversation_id="NAO_EXISTE") == []
    assert gw.get_mensagens("NAO_EXISTE") == []
    assert gw.get_reenvios("GXH000000") == []


def test_get_pedido_com_as_of_devolve_o_pedido_naquela_data():
    gw = _gw()
    conv = gw.get_conversa("CV000001")
    as_of = datetime.fromisoformat(conv["data_abertura"])
    bruto = _ds().pedidos[conv["order_id"]]
    assert gw.get_pedido(conv["order_id"], as_of=as_of) == pedido_as_of(bruto, as_of)
    assert gw.get_pedido(conv["order_id"]) == bruto


def test_fila_tem_as_65_conversas():
    assert len(_gw().fila()) == 65


def test_agora_e_data_abertura_no_historico_e_now_na_fila():
    gw = _gw()
    _, now_fila, origem_fila = conversa_e_agora(gw, "CV000033")
    conv, now_hist, origem_hist = conversa_e_agora(gw, "CV000001")
    assert (now_fila, origem_fila) == (NOW, "fila")
    assert (now_hist, origem_hist) == (datetime.fromisoformat(conv["data_abertura"]), "historico")


def test_get_rastreio_ignora_eventos_depois_de_as_of():
    gw = _gw()
    eventos = gw.get_rastreio("PED000022")  # pedido de CV000011
    assert [e["status"] for e in eventos] == ["coletado", "em_transferencia"]
    assert [e["status"] for e in gw.get_rastreio("PED000022", as_of=datetime(2026, 10, 25))]         == ["coletado"]
    assert gw.get_rastreio("GXH000000") == []


@pytest.mark.parametrize("cid,dias", [
    ("CV000011", 5),  # último evento em_transferencia em 25/10; 02/11 é feriado
    ("CV000033", 0),  # N01
    ("CV000015", 0),  # N02
])
def test_build_case_conta_dias_uteis_sem_movimento_do_rastreio(cid, dias):
    gw = _gw()
    conv = gw.get_conversa(cid)
    case = build_case(gw, cid, NOW, _cl(), conv["order_id"], POLICY)
    assert case.dias_uteis_sem_movimento == dias


def test_rastreio_entregue_nao_conta_como_parado():
    gw = _gw()
    oid = next(o for o, evs in _ds().rastreio.items() if evs[-1]["status"] == "entregue")
    conv = next(c for c in gw.fila() if c["order_id"])
    case = build_case(gw, conv["conversation_id"], NOW, _cl(), oid, POLICY)
    assert case.dias_uteis_sem_movimento is None


def test_build_case_corta_pedido_e_eventos_na_data_da_conversa():
    gw = _gw()
    conv, now, _ = conversa_e_agora(gw, "CV000003")  # N06, histórico
    case = build_case(gw, "CV000003", now, _cl("arrependimento_cancelamento"), conv["order_id"],
                      POLICY)
    assert case.now == now
    assert case.pedido == pedido_as_of(_ds().pedidos[conv["order_id"]], now)
    assert all(datetime.fromisoformat(p["data_hora_criacao"]) <= now for p in case.pagamentos)
    assert case.valor == float(case.pedido["valor"])


def test_build_case_sem_pedido_nao_consulta_nada_do_pedido():
    gw = _gw()
    case = build_case(gw, "CV000032", NOW, _cl("duvida_produto"), "", POLICY)
    assert case.pedido is None and case.valor == 0.0 and case.dias_uteis_sem_movimento is None
    assert case.reenvios_anteriores == case.pagamentos == case.estornos == case.itens == []


# --- o pipeline não depende de CSV ---

def _classify_fixo(texto, conversation_id):
    return Classificacao("onde_esta_pedido", None, None, [], 0.9)


def test_fake_gateway_sem_csv_produz_o_mesmo_case_result():
    from dataclasses import asdict

    from fakes import copiar_do_csv
    from pipeline.policy import load_policy
    from pipeline.run import run_conversation, run_queue
    from pipeline.tools import ToolBox

    policy = load_policy()
    ids = ["CV000033", "CV000037", "CV000032", "CV000011"]  # N01, N03, sem pedido, parado
    csv_gw = CsvGateway(_ds(), ToolBox("atendente", policy))
    fake = copiar_do_csv(csv_gw, ids, policy)
    assert isinstance(fake, Gateway)
    def sem_tempo(r):  # o log traz ms medidos, que variam entre execuções
        d = asdict(r)
        d["log"] = [{**x, "ms": 0} for x in d["log"]]
        return d
    for cid in ids:
        assert sem_tempo(run_conversation(fake, policy, _classify_fixo, cid)) == \
            sem_tempo(run_conversation(csv_gw, policy, _classify_fixo, cid))
    resultados = run_queue(fake, policy, _classify_fixo)
    assert sorted(r.conversation_id for r in resultados) == sorted(ids)
