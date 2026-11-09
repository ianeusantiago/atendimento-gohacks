import inspect

import pytest

from pipeline.data import read_csv
from pipeline.policy import load_policy
from pipeline.tools import FERRAMENTAS, LimitExceeded, MissingParam, NotPermitted, ToolBox

POLICY = load_policy()
CSV = {r["ferramenta"]: r for r in read_csv("ferramentas.csv")}


def _box(role="atendente"):
    return ToolBox(role, POLICY)


def test_reenvio_acima_do_limite_sem_aprovacao_levanta():
    with pytest.raises(LimitExceeded):
        _box().reenviar_produto(order_id="X", valor=250, motivo="avaria")


def test_reenvio_acima_do_limite_com_aprovacao_passa():
    aprovadas = set()
    ToolBox("supervisor", POLICY, aprovadas=aprovadas).aprovar_acao(aprovacao_id="A1")
    call = ToolBox("atendente", POLICY, aprovadas=aprovadas).reenviar_produto(
        order_id="X", valor=250, motivo="avaria", aprovacao_id="A1")
    assert call["tool"] == "reenviar_produto" and call["params"]["aprovacao_id"] == "A1"


def test_aprovacao_inventada_nao_libera_valor_acima_do_limite():
    with pytest.raises(LimitExceeded):
        _box().reembolsar(order_id="X", valor=500, motivo="x", aprovacao_id="qualquer")


def test_acionar_pessoa_recusa_area_fora_de_ferramentas_csv():
    with pytest.raises(MissingParam):
        _box().acionar_pessoa(area="atendimento", assunto="a", contexto="c")
    assert _box().acionar_pessoa(area="supervisao", assunto="a", contexto="c")


def test_reembolso_usa_o_limite_proprio_de_ferramentas_csv():
    with pytest.raises(LimitExceeded):
        _box().reembolsar(order_id="X", valor=100.01, motivo="duplicidade")
    assert _box().reembolsar(order_id="X", valor=100.0, motivo="duplicidade")["role"] == "atendente"


def test_aprovar_acao_com_atendente_levanta_not_permitted():
    with pytest.raises(NotPermitted):
        _box().aprovar_acao(aprovacao_id="A1")
    assert _box("supervisor").aprovar_acao(aprovacao_id="A1")["role"] == "supervisor"


def test_cosmetovigilancia_so_com_supervisor():
    params = dict(conversation_id="AT1", sku="GBT-1", descricao="relato")
    for papel in ("atendente", "analista"):
        with pytest.raises(NotPermitted):
            _box(papel).registrar_cosmetovigilancia(**params)
    assert _box("supervisor").registrar_cosmetovigilancia(**params)["tool"] == \
        "registrar_cosmetovigilancia"


def test_calls_registram_ferramenta_params_papel_e_ts():
    box = _box()
    box.informar_status(conversation_id="AT1", order_id="GBH1")
    box.solicitar_foto(conversation_id="AT1")
    assert [c.tool for c in box.calls] == ["informar_status", "solicitar_foto"]
    assert box.calls[0].params == {"conversation_id": "AT1", "order_id": "GBH1"}
    assert box.calls[0].role == "atendente" and box.calls[0].ts
    assert "do_que" not in box.calls[1].params  # opcional ausente não vira None


def test_parametro_obrigatorio_vazio_levanta():
    with pytest.raises(MissingParam):
        _box().responder_cliente(conversation_id="AT1", texto="")


def test_chamada_negada_nao_fica_registrada():
    box = _box()
    with pytest.raises(LimitExceeded):
        box.reenviar_produto(order_id="X", valor=250, motivo="avaria")
    assert box.calls == []


def test_papel_desconhecido_levanta():
    with pytest.raises(ValueError):
        ToolBox("estagiario", POLICY)


def test_papeis_e_limites_vem_de_ferramentas_csv():
    assert FERRAMENTAS["reembolsar"].valor_max == 100.0
    assert FERRAMENTAS["reenviar_produto"].valor_max == 200.0
    assert FERRAMENTAS["acionar_pessoa"].papeis == {"atendente", "analista", "supervisor"}
    assert FERRAMENTAS["registrar_cosmetovigilancia"].papeis == {"supervisor"}
    assert set(FERRAMENTAS) == set(CSV)


def test_cada_metodo_tem_os_parametros_de_ferramentas_csv():
    metodos = [n for n, _ in inspect.getmembers(ToolBox, inspect.isfunction)
               if not n.startswith("_")]
    assert len(metodos) >= 20
    for nome in metodos:
        assert nome in CSV, nome
        sig = inspect.signature(getattr(ToolBox, nome)).parameters
        params = [p for p in sig if p != "self"]
        esperados = [p.strip() for p in CSV[nome]["parametros"].split(";") if p.strip()]
        assert params == [p.rstrip("*") for p in esperados], nome
        for p in esperados:
            obrigatorio = p.endswith("*")
            assert (sig[p.rstrip("*")].default is inspect.Parameter.empty) == obrigatorio, \
                (nome, p)
