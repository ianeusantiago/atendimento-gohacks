import json
import re
from functools import lru_cache

import pytest
from jsonschema import Draft202012Validator

from pipeline import export
from pipeline.cli import classify_from_fallback
from pipeline.data import load_dataset
from pipeline.export import PIILeak, export_public, montar, summarize
from pipeline.gateway import CsvGateway
from pipeline.policy import load_policy
from pipeline.respostas import em_analise
from pipeline.run import CaseResult, run_queue
from pipeline.tools import ToolBox

POLICY = load_policy()
SCHEMA = json.loads(export.SCHEMA_PATH.read_text(encoding="utf-8"))
IDS = re.compile(r"AT\d{6}|G[CB]H\d+|CH\d{6}")


def _r(cid="CV000009", prioridade=1, ferramenta="informar_status", motivo="Pedido em trânsito.",
       resposta="Olá! Seu pedido PED000003 está em trânsito.", enviada=True, calls=None,
       evidencias=(), regra="onde_esta_pedido", params=None, marca="Lumen"):
    return CaseResult(
        conversation_id=cid, canal="whatsapp", prioridade=prioridade,
        classificacao={"categoria": "onde_esta_pedido", "categoria_secundaria": None,
                       "order_id": "PED000003", "sinais_risco": [], "confianca": 0.9},
        decisao={"acao": ferramenta, "ferramenta": ferramenta, "params": params or {},
                 "motivo": motivo, "regra": regra},
        calls=calls if calls is not None else [
            {"tool": "classificar_conversa", "params": {"conversation_id": cid},
             "status": "executada"},
            {"tool": ferramenta, "params": {"order_id": "PED000003"}, "status": "executada"}],
        evidencias=list(evidencias),
        resposta_cliente={"texto": resposta, "enviada": enviada} if resposta else None,
        marca=marca, dados=[{"rotulo": "Status do pedido", "valor": "em_transito"}],
        log=[{"etapa": "decidir", "resultado": ferramenta, "ms": 0.4}])


def test_piileak_quando_um_motivo_tem_cpf(tmp_path):
    saida = tmp_path / "results.json"
    with pytest.raises(PIILeak):
        export_public([_r(motivo="Cliente informou o CPF 123.456.789-09.")], saida)
    assert not saida.exists()  # nada é gravado


def test_piileak_com_telefone_ou_cartao_em_qualquer_campo(tmp_path):
    with pytest.raises(PIILeak):
        export_public([_r(resposta="Ligue para (11) 98765-4321")], tmp_path / "a.json")
    with pytest.raises(PIILeak):
        export_public([_r(evidencias=[{"kind": "x", "detail": "4111 1111 1111 1111"}])],
                      tmp_path / "b.json")


def test_ids_originais_viram_pseudonimos(tmp_path):
    saida = tmp_path / "results.json"
    r1 = _r("CV000009", 2, motivo="A conversa CV000010 cita o pedido PED000051; reenvio "
                                   "OMS000613.")
    r2 = _r("CV000010", 1, motivo="Outra conversa CV000001 do cliente CH761018.")
    export_public([r1, r2], saida)
    texto = saida.read_text(encoding="utf-8")
    assert not IDS.search(texto)
    assert "OMS000613" not in texto
    doc = json.loads(texto)
    assert [it["alias"] for it in doc["itens"]] == ["CONV-001", "CONV-002"]
    assert re.fullmatch(r"A conversa CONV-001 cita o pedido PED-\d{3}; reenvio REF-\d{3}\.",
                        doc["itens"][1]["motivo"])
    assert re.fullmatch(r"Outra conversa HIST-001 do cliente C-001\.", doc["itens"][0]["motivo"])
    assert re.search(r"pedido PED-\d{3} está", doc["itens"][0]["resposta_cliente"])


def test_destino_e_acoes_secundarias():
    aprov = _r("AT1", 1, "solicitar_aprovacao", params={"acao": "reembolsar"})
    pessoa = _r("AT2", 2, "acionar_pessoa", calls=[
        {"tool": "validar_cupom", "params": {}, "status": "pendente"},
        {"tool": "acionar_pessoa", "params": {}, "status": "executada"},
        {"tool": "responder_cliente", "params": {}, "status": "executada"}])
    sup = _r("AT3", 3, "sinalizar_suspeita", resposta=em_analise(POLICY), enviada=False)
    auto = _r("AT4", 4)
    itens = montar([aprov, pessoa, sup, auto])["itens"]
    assert [i["destino"] for i in itens] == ["aprovacao", "pessoa", "supervisor", "automatico"]
    assert itens[0]["acoes_secundarias"] == ["reembolsar"]
    assert itens[1]["acoes_secundarias"] == ["validar_cupom"]
    assert itens[2]["resposta_cliente"] == em_analise(POLICY)
    assert itens[3]["acoes_secundarias"] == []


def test_marca_grupo():
    assert export.marca_grupo("Modaviva") == "Modaviva"
    assert export.marca_grupo("Lótus") == "Belleza"


def test_resumo_igual_a_summarize_e_schema_valido(tmp_path):
    saida = tmp_path / "results.json"
    export_public([_r("AT1", 1), _r("AT2", 2, "acionar_pessoa")], saida)
    doc = json.loads(saida.read_text(encoding="utf-8"))
    Draft202012Validator(SCHEMA).validate(doc)
    assert doc["resumo"] == summarize(doc["itens"]) == {
        "total": 2, "automaticas": 1, "aprovacao": 0, "pessoa": 1, "supervisor": 0}
    assert set(doc["itens"][0]) == set(SCHEMA["$defs"]["item"]["required"])


@lru_cache(maxsize=1)
def _fila_real():
    gw = CsvGateway(load_dataset(), ToolBox("atendente", POLICY))
    return run_queue(gw, POLICY, classify_from_fallback())


def test_export_da_fila_real_sem_ids_nem_pii(tmp_path):
    saida = tmp_path / "results.json"
    resultados = _fila_real()
    export_public(resultados, saida)
    texto = saida.read_text(encoding="utf-8")
    assert not IDS.search(texto)
    assert not re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", texto)
    assert not re.search(r"\(?\d{2}\)?\s?9?\d{4}-?\d{4}", texto)
    assert not re.search(r"\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}", texto)
    doc = json.loads(texto)
    assert doc["resumo"]["total"] == 65
    assert [i["prioridade"] for i in doc["itens"]] == list(range(1, 66))
    for it, r in zip(doc["itens"], sorted(resultados, key=lambda r: r.prioridade)):
        assert it["acao"] == r.decisao["ferramenta"]
        assert [x["etapa"] for x in it["log"]][:2] == ["mascarar", "classificar"]
    # nenhum texto de mensagem de cliente
    gw = CsvGateway(load_dataset())
    for r in resultados:
        for m in gw.get_mensagens(r.conversation_id):
            if m["autor"] == "cliente" and len(m["texto"]) > 30:
                assert m["texto"] not in texto
