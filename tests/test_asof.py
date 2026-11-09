from datetime import datetime
from functools import lru_cache

import pytest

from helpers import case_da_conversa
from pipeline.asof import anexos_ate, eventos_ate, pedido_as_of
from pipeline.config import NOW
from pipeline.data import load_dataset
from pipeline.models import Classificacao


def _pedido(**campos):
    base = {"order_id": "GBHT00001", "status_entrega": "entregue",
            "data_separacao": "2026-10-10 10:00:00", "data_entrega": "2026-10-15"}
    base.update(campos)
    return base


@pytest.mark.parametrize("as_of,status,separacao,entrega", [
    (datetime(2026, 10, 9, 8), "aguardando_separacao", "", ""),
    (datetime(2026, 10, 10, 10), "em_transito", "2026-10-10 10:00:00", ""),
    (datetime(2026, 10, 14, 23, 59), "em_transito", "2026-10-10 10:00:00", ""),
    (datetime(2026, 10, 15, 0, 1), "entregue", "2026-10-10 10:00:00", "2026-10-15"),
])
def test_pedido_as_of_deriva_status_e_apaga_datas_futuras(as_of, status, separacao, entrega):
    p = pedido_as_of(_pedido(), as_of)
    assert (p["status_entrega"], p["data_separacao"], p["data_entrega"]) == \
        (status, separacao, entrega)


def test_pedido_as_of_nao_altera_o_original():
    original = _pedido()
    pedido_as_of(original, datetime(2026, 10, 1))
    assert original == _pedido()


@pytest.mark.parametrize("status", ["devolvido", "cancelado", "extraviado"])
def test_status_final_so_vale_no_retrato(status):
    # Sem data própria de devolução, cancelamento ou extravio: antes do retrato (NOW) o status
    # vem só das datas que existem.
    p = _pedido(status_entrega=status)
    assert pedido_as_of(p, NOW)["status_entrega"] == status
    assert pedido_as_of(p, datetime(2026, 10, 20))["status_entrega"] == "entregue"
    assert pedido_as_of(p, datetime(2026, 10, 12))["status_entrega"] == "em_transito"


def test_eventos_ate_corta_pela_data_e_descarta_sem_data():
    rows = [{"id": "a", "d": "2026-10-01 10:00:00"}, {"id": "b", "d": "2026-10-02 10:00:00"},
            {"id": "c", "d": "2026-10-02"}, {"id": "d", "d": ""}]
    assert [r["id"] for r in eventos_ate(rows, datetime(2026, 10, 2, 9), "d")] == ["a", "c"]
    assert [r["id"] for r in eventos_ate(rows, datetime(2026, 10, 2, 10), "d")] == ["a", "b", "c"]


def _anx(anexo_id, conversa, enviado_em):
    return {"anexo_id": anexo_id, "conversation_id": conversa, "enviado_em": enviado_em}


ABERTURA = datetime(2026, 8, 6, 15, 53, 56)


def test_anexos_ate_corta_outras_conversas_e_mantem_a_propria():
    base = [_anx("PROPRIO_DEPOIS", "ATX1", "2026-08-06 17:33:00"),   # (ii) fica
            _anx("OUTRO_DEPOIS", "ATX2", "2026-08-31 11:48:38"),     # (i) sai
            _anx("OUTRO_ANTES", "ATX3", "2026-08-01 10:00:00"),      # (iii) fica
            _anx("OUTRO_NO_INSTANTE", "ATX4", "2026-08-06 15:53:56"),  # (iii) fica
            _anx("OUTRO_SEM_DATA", "ATX5", "")]
    assert [a["anexo_id"] for a in anexos_ate(base, "ATX1", ABERTURA)] ==         ["PROPRIO_DEPOIS", "OUTRO_ANTES", "OUTRO_NO_INSTANTE"]


def test_anexos_ate_no_retrato_nao_muda_a_fila():
    todos = _ds().todos_anexos
    assert anexos_ate(todos, "CV000039", NOW) == todos


# --- dados reais ---

@lru_cache(maxsize=1)
def _ds():
    return load_dataset()


def test_no_retrato_o_pedido_fica_igual():
    assert all(pedido_as_of(p, NOW) == p for p in _ds().pedidos.values())


def _cl(categoria, order_id):
    return Classificacao(categoria=categoria, categoria_secundaria=None, order_id=order_id,
                         confianca=0.9)


def test_case_d04_fila_traz_anexos_e_reenvio_do_pedido():
    # D04 (CV000039, fila): a conversa não tem anexo; a foto foi enviada em CV000008 (27/10).
    case = case_da_conversa(_ds(), "CV000039", _cl("item_faltante", "PED000006"))
    assert case.now == NOW
    assert {a["anexo_id"] for a in case.anexos} == {"IMG000349", "IMG000350"}
    assert [(r["solicitacao_id"], r["sku_enviado"]) for r in case.reenvios_anteriores] == \
        [("OMS000613", "KSH-5002")]
    assert ("GBT-9001", "brinde") in {(i["sku"], i["tipo_item"]) for i in case.itens}


def test_case_n06_historico_na_data_da_conversa():
    # N06 (CV000003): aberta em 09/08 23:59:58; o estorno EST000015 foi pedido em 10/08.
    case = case_da_conversa(_ds(), "CV000003", _cl("arrependimento_cancelamento", "PED000040"))
    assert case.now == datetime(2026, 8, 9, 23, 59, 58)
    assert case.pedido["status_entrega"] == "entregue"  # devolvido só no retrato de 02/11
    assert [t["transacao_id"] for t in case.pagamentos] == ["TRX00001421", "TRX00001422"]
    assert case.estornos == []
    assert case.valor == 99.66
