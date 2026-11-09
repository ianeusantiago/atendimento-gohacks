import csv
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pytest

from fakes import FakeGateway
from pipeline import run
from pipeline.config import NOW
from pipeline.data import load_dataset, read_csv
from pipeline.gateway import CsvGateway
from pipeline.mask import contains_pii
from pipeline.models import Classificacao, Escalation
from pipeline.policy import load_policy
from pipeline.run import CaseResult, priority_key, run_conversation, run_queue
from pipeline.sla import prazo_primeira_resposta
from pipeline.tools import FERRAMENTAS, ToolBox

POLICY = load_policy()
ROOT = Path(__file__).resolve().parent.parent
FINANCEIRAS = {"reenviar_produto", "reimprimir_personalizacao", "trocar_produto", "reembolsar"}
CPF, TEL, CARTAO = "123.456.789-09", "(11) 98765-4321", "4111 1111 1111 1111"


def _conv(cid, order_id="", canal="email", abertura="2026-11-01 10:00:00", cliente="C1"):
    return {"conversation_id": cid, "customer_id": cliente, "order_id": order_id,
            "marca": "Lumen", "canal": canal, "data_abertura": abertura,
            "status": "aberto", "assunto": "x"}


def _msg(cid, texto, autor="cliente", i=1):
    return {"conversation_id": cid, "message_id": f"{cid}-{i}", "autor": autor,
            "timestamp": f"2026-11-01 10:0{i}:00", "texto": texto}


def _pedido(order_id="PED000001", cliente="C1", **campos):
    base = {"order_id": order_id, "customer_id": cliente, "marca": "Lumen",
            "data_pedido": "2026-10-28", "valor": "150.00", "sku": "GBT-1",
            "descricao_produto": "Body Mist Baunilha 200ml", "personalizacao": "",
            "transportadora": "TransLeste", "uf": "SP", "status_entrega": "em_transito",
            "data_separacao": "2026-10-28 10:00:00", "data_entrega": "", "lote_produto": "L42"}
    base.update(campos)
    return base


def _cliente(cid="C1"):
    return {"customer_id": cid, "nome": "Fulana", "cpf": CPF, "telefone": TEL}


def _cl(categoria="onde_esta_pedido", order_id=None, sinais=(), confianca=0.9):
    return Classificacao(categoria, None, order_id, list(sinais), confianca)


def _fixo(mapa):
    """classify_fn falso: conversation_id -> Classificacao | Escalation | Exception."""
    recebidos = {}

    def fn(texto, conversation_id):
        recebidos[conversation_id] = texto
        r = mapa[conversation_id]
        if isinstance(r, Exception):
            raise r
        return r
    fn.recebidos = recebidos
    return fn


def _tools(r: CaseResult, status="executada"):
    return [c["tool"] for c in r.calls if c["status"] == status]


# --- Review Focus 1: conversa sem pedido ---

def test_sem_order_id_e_sem_pedido_citado_pede_o_pedido_sem_consultar():
    gw = FakeGateway(fila=[_conv("A1")], mensagens={"A1": [_msg("A1", "cadê minha compra?")]},
                     clientes=[_cliente()])
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl()}), "A1")
    assert r.decisao["ferramenta"] == "responder_cliente"
    assert "responder_cliente" in _tools(r)
    assert "número do pedido" in r.resposta_cliente["texto"]
    assert gw.pedidos_consultados == []
    assert not set(_tools(r)) & (FINANCEIRAS | {"informar_status", "acionar_pessoa"})


def test_pedido_que_nao_aparece_no_texto_nao_e_usado():
    # O classificador "achou" um pedido que o cliente não escreveu: nunca inventar.
    gw = FakeGateway(fila=[_conv("A1")], mensagens={"A1": [_msg("A1", "cadê minha compra?")]},
                     pedidos=[_pedido()], clientes=[_cliente()])
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl(order_id="PED000001")}), "A1")
    assert r.decisao["ferramenta"] == "responder_cliente"
    assert gw.pedidos_consultados == []


def test_pedido_citado_inexistente_pede_para_conferir_o_numero():
    gw = FakeGateway(fila=[_conv("A1")], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", "pedido PED000039 não chegou")]})
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl(order_id="PED000039")}), "A1")
    assert r.decisao["ferramenta"] == "responder_cliente"
    assert "Não localizamos" in r.resposta_cliente["texto"]


# --- Review Focus 2: pedido de outro cliente ---

def test_pedido_citado_de_outro_cliente_vai_para_pessoa_sem_agir():
    gw = FakeGateway(fila=[_conv("A1")], clientes=[_cliente(), _cliente("C2")],
                     mensagens={"A1": [_msg("A1", "meu pedido PED000002 chegou quebrado")]},
                     pedidos=[_pedido("PED000002", cliente="C2")])
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl("avaria_vazamento", "PED000002")}), "A1")
    assert r.decisao["ferramenta"] == "acionar_pessoa"
    assert r.decisao["regra"] == "pedido_de_outro_cliente"
    assert set(_tools(r)) <= {"classificar_conversa", "acionar_pessoa", "responder_cliente"}
    texto = json.dumps(asdict(r), ensure_ascii=False)
    assert "Body Mist" not in texto and "TransLeste" not in texto  # nada do pedido alheio


def test_pedido_vinculado_de_outro_cliente_tambem_vai_para_pessoa():
    gw = FakeGateway(fila=[_conv("A1", order_id="PED000002")], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", "onde está?")]},
                     pedidos=[_pedido("PED000002", cliente="C2")])
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl()}), "A1")
    assert r.decisao["regra"] == "pedido_de_outro_cliente"


# --- Review Focus 4: falhas viram pessoa e a fila continua ---

def _fila_de_tres(**kw):
    convs = [_conv("A1", "PED000001"), _conv("A2", "PED000001"), _conv("A3", "PED000001")]
    return FakeGateway(fila=convs, pedidos=[_pedido()], clientes=[_cliente()],
                       mensagens={c["conversation_id"]: [_msg(c["conversation_id"], "oi")]
                                  for c in convs}, **kw)


def test_escalation_do_classificador_vai_para_pessoa_e_a_fila_segue():
    fn = _fixo({"A1": _cl(), "A2": Escalation("modelo indisponivel: timeout"), "A3": _cl()})
    rs = {r.conversation_id: r for r in run_queue(_fila_de_tres(), POLICY, fn)}
    assert rs["A2"].decisao["ferramenta"] == "acionar_pessoa"
    assert "timeout" in rs["A2"].decisao["motivo"]
    assert rs["A1"].decisao["ferramenta"] == rs["A3"].decisao["ferramenta"] == "informar_status"


def test_excecao_no_classificador_vira_pessoa_so_com_o_tipo():
    fn = _fixo({"A1": _cl(), "A2": RuntimeError(f"vazou {CPF} sk-token"), "A3": _cl()})
    rs = {r.conversation_id: r for r in run_queue(_fila_de_tres(), POLICY, fn)}
    assert rs["A2"].decisao["ferramenta"] == "acionar_pessoa"
    assert "RuntimeError" in rs["A2"].decisao["motivo"]
    dump = json.dumps(asdict(rs["A2"]), ensure_ascii=False)
    assert "vazou" not in dump and "sk-token" not in dump and not contains_pii(dump)
    assert rs["A3"].decisao["ferramenta"] == "informar_status"


def test_falha_ao_executar_ferramenta_vira_pessoa():
    gw = _fila_de_tres(falhar_em={"informar_status"})
    rs = run_queue(gw, POLICY, _fixo({c: _cl() for c in ("A1", "A2", "A3")}))
    assert len(rs) == 3
    for r in rs:
        assert r.decisao["ferramenta"] == "acionar_pessoa"
        assert "ConnectionError" in r.decisao["motivo"]
        assert "acionar_pessoa" in _tools(r)


def test_falha_ate_no_acionar_pessoa_fica_registrada_como_pendente():
    gw = _fila_de_tres(falhar_em={"informar_status", "acionar_pessoa"})
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl()}), "A1")
    assert r.decisao["ferramenta"] == "acionar_pessoa"
    assert "acionar_pessoa" in _tools(r, "pendente")


# --- (d) ordem da fila ---

def _res(cid, canal, minutos, categoria="onde_esta_pedido"):
    return CaseResult(cid, canal, 0, {"categoria": categoria, "categoria_secundaria": None,
                                      "sinais_risco": []}, {}, [], [],
                      sla_minutos_restantes=minutos)


def test_priority_key_reacao_adversa_e_reclame_aqui_primeiro_depois_sla():
    itens = [_res("E1", "email", 5), _res("W1", "whatsapp", -30),
             _res("R1", "reclame_aqui", 600), _res("R2", "reclame_aqui", 10),
             _res("X1", "email", 900, "reacao_adversa"), _res("E0", "email", None)]
    ordem = [r.conversation_id for r in sorted(itens, key=priority_key)]
    assert ordem == ["X1", "R2", "R1", "W1", "E1", "E0"]


def test_run_queue_sai_ordenada_com_prioridade_1_a_n():
    convs = [_conv("A1", canal="email", abertura="2026-11-01 09:00:00"),
             _conv("A2", canal="reclame_aqui", abertura="2026-11-01 12:00:00"),
             _conv("A3", canal="whatsapp", abertura="2026-11-01 19:50:00"),
             _conv("A4", canal="email", abertura="2026-11-01 08:00:00")]
    gw = FakeGateway(fila=convs, clientes=[_cliente()],
                     mensagens={c["conversation_id"]: [_msg(c["conversation_id"], "oi")]
                                for c in convs})
    fn = _fixo({"A1": _cl("elogio"), "A2": _cl("elogio"), "A3": _cl("elogio"),
                "A4": _cl("reacao_adversa")})
    rs = run_queue(gw, POLICY, fn)
    assert [r.conversation_id for r in rs] == ["A4", "A2", "A3", "A1"]
    assert [r.prioridade for r in rs] == [1, 2, 3, 4]
    assert rs == sorted(rs, key=priority_key)


def test_sla_whatsapp_conta_so_o_horario_de_atendimento():
    # 30 min (politicas.csv); aberta 19:50 -> 10 min hoje + 20 min a partir das 08:00.
    assert prazo_primeira_resposta("whatsapp", datetime(2026, 11, 1, 19, 50), POLICY) == \
        datetime(2026, 11, 2, 8, 20)
    assert prazo_primeira_resposta("whatsapp", datetime(2026, 11, 1, 6, 0), POLICY) == \
        datetime(2026, 11, 1, 8, 30)
    assert prazo_primeira_resposta("email", datetime(2026, 11, 1, 10, 0), POLICY) == \
        datetime(2026, 11, 2, 10, 0)
    assert prazo_primeira_resposta("reclame_aqui", datetime(2026, 11, 1, 10, 0), POLICY) == \
        datetime(2026, 11, 3, 10, 0)


# --- (e) sem PII; texto ao classificador mascarado, só do cliente, truncado ---

def test_resultado_sem_pii_e_classificador_so_recebe_texto_mascarado_do_cliente():
    msgs = [_msg("A1", f"meu cpf {CPF}, tel {TEL}, cartão {CARTAO}", i=1),
            _msg("A1", "texto do bot", autor="bot", i=2),
            _msg("A1", "x" * 10000, i=3)]
    gw = FakeGateway(fila=[_conv("A1", "PED000001")], pedidos=[_pedido()],
                     clientes=[_cliente()], mensagens={"A1": msgs})
    fn = _fixo({"A1": _cl()})
    rs = run_queue(gw, POLICY, fn)
    enviado = fn.recebidos["A1"]
    assert not contains_pii(enviado) and "[CPF]" in enviado
    assert "texto do bot" not in enviado
    assert len(enviado) <= run.MAX_CHARS_CLASSIFICADOR
    dump = json.dumps([asdict(r) for r in rs], ensure_ascii=False)
    assert not contains_pii(dump) and "Fulana" not in dump


def test_conversa_so_com_bot_encerra_sem_chamar_o_modelo():
    gw = FakeGateway(fila=[_conv("A1")], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", "Olá! Como posso ajudar?", autor="bot")]})
    fn = _fixo({})
    r = run_conversation(gw, POLICY, fn, "A1")
    assert fn.recebidos == {}
    assert r.decisao["ferramenta"] == "encerrar_conversa"
    assert r.classificacao["categoria"] == "sem_interacao"


# --- reação adversa e suspeita ---

def test_reacao_adversa_orienta_e_deixa_cosmetovigilancia_pendente_para_supervisor():
    gw = FakeGateway(fila=[_conv("A1", "PED000001", canal="whatsapp")], pedidos=[
        _pedido(status_entrega="entregue", data_entrega="2026-10-30")], clientes=[_cliente()],
        mensagens={"A1": [_msg("A1", "deu alergia")]})
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl("reacao_adversa")}), "A1")
    assert "orientar_suspensao_uso" in _tools(r) and "acionar_pessoa" in _tools(r)
    pend = next(c for c in r.calls if c["tool"] == "registrar_cosmetovigilancia")
    assert pend["status"] == "pendente" and pend["role"] == "supervisor"
    assert pend["params"]["sku"] == "GBT-1" and pend["params"]["lote"] == "L42"
    assert pend["params"]["descricao"] and pend["params"]["conversation_id"] == "A1"
    horas = POLICY.categorias["reacao_adversa"]["prazo_registro_horas"]
    # verificação item 3a: o prazo conta do relato (abertura 01/11 10:00), não do "agora"
    relato = datetime.fromisoformat("2026-11-01 10:00:00")
    assert pend["prazo"] == (relato + timedelta(hours=horas)).isoformat()
    assert "registrar_cosmetovigilancia" not in [c.tool for c in gw.toolbox.calls]


@pytest.mark.parametrize("dono", ["C1", "C2"])
def test_reacao_adversa_com_pedido_citado_divergente_mantem_acoes_obrigatorias(dono):
    # verificação item 3b: pedido divergente ou de outro cliente não apaga a reação adversa
    gw = FakeGateway(fila=[_conv("A1", "PED000001")], pedidos=[
        _pedido(status_entrega="entregue", data_entrega="2026-10-30"),
        _pedido(order_id="PED000002", cliente=dono)], clientes=[_cliente()],
        mensagens={"A1": [_msg("A1", "deu alergia com o PED000002")]})
    cl = _cl("reacao_adversa", order_id="PED000002")
    r = run_conversation(gw, POLICY, _fixo({"A1": cl}), "A1")
    assert "orientar_suspensao_uso" in _tools(r) and "acionar_pessoa" in _tools(r)
    pend = next(c for c in r.calls if c["tool"] == "registrar_cosmetovigilancia")
    assert pend["status"] == "pendente" and pend["role"] == "supervisor"
    assert "PED000002" in r.decisao["motivo"]


@lru_cache(maxsize=1)
def _csv_gw():
    return CsvGateway(load_dataset(), ToolBox("atendente", POLICY))


def test_sinalizar_suspeita_no_historico_nao_envia_nada_ao_cliente():
    gw = _csv_gw()
    conv = gw.get_conversa("CV000001")  # D01
    r = run_conversation(gw, POLICY, _fixo({"CV000001": _cl("avaria_vazamento")}), "CV000001")
    assert r.decisao["ferramenta"] == "sinalizar_suspeita" and r.origem == "historico"
    assert r.data_abertura == conv["data_abertura"]
    assert "responder_cliente" not in _tools(r)
    assert r.resposta_cliente["enviada"] is False
    assert "em análise" in r.resposta_cliente["texto"]
    assert r.evidencias and all(e["kind"] for e in r.evidencias)


# --- contrato das chamadas e casos de avaliação pelo pipeline inteiro ---

def _casos():
    with open(ROOT / "evals" / "casos.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("caso", [c for c in _casos() if c["caso_id"] not in ("A01", "A02")],
                         ids=lambda c: c["caso_id"])
def test_casos_de_avaliacao_pelo_run_conversation(caso):
    cid = caso["conversation_id"]
    r = run_conversation(_csv_gw(), POLICY, _fixo({cid: _cl(caso["categoria_esperada"])}), cid)
    assert r.decisao["acao"] == caso["acao_esperada"]
    _confere_contrato(r)


def _confere_contrato(r: CaseResult):
    if r.decisao["ferramenta"] == "acionar_pessoa":
        assert {"area", "assunto", "contexto"} <= set(r.decisao["params"])
    for c in r.calls:
        spec = FERRAMENTAS[c["tool"]]
        if "conversation_id" in spec.parametros:
            assert c["params"]["conversation_id"] == r.conversation_id, c
        if c["tool"] == "acionar_pessoa":
            p = c["params"]
            assert p["area"] and p["assunto"] and p["contexto"]
            assert len(p["contexto"]) <= run.MAX_CONTEXTO and not contains_pii(p["contexto"])
        assert set(c["params"]) <= set(spec.parametros), c


# --- fallback: classificações reais salvas ---

FALLBACK = ROOT / "fallback" / "classificacoes.json"
CAMPOS = {"categoria", "categoria_secundaria", "order_id", "sinais_risco", "confianca"}


def test_fallback_so_tem_ids_e_campos_derivados():
    dados = json.loads(FALLBACK.read_text(encoding="utf-8"))
    from pipeline.cli import historico_dos_casos
    fila = {c["conversation_id"] for c in read_csv("fila_aberta.csv")}
    # fila + conversas do histórico usadas em evals/casos.csv (classificadas para os evals)
    assert dados and set(dados) <= fila | set(historico_dos_casos())
    for cid, cl in dados.items():
        assert set(cl) == CAMPOS, cid
    assert not contains_pii(FALLBACK.read_text(encoding="utf-8"))


def test_fallback_reproduz_as_mesmas_decisoes_e_respeita_o_contrato():
    fn = run.classify_from_fallback(FALLBACK)
    dados = json.loads(FALLBACK.read_text(encoding="utf-8"))
    em_memoria = _fixo({cid: Classificacao(**cl) for cid, cl in dados.items()})

    def outro(texto, cid):
        return em_memoria(texto, cid) if cid in dados else Escalation("sem classificacao")
    a = [asdict(r) for r in run_queue(_csv_gw(), POLICY, fn)]
    b = [asdict(r) for r in run_queue(_csv_gw(), POLICY, outro)]
    assert len(a) == 65
    assert [(x["conversation_id"], x["decisao"]) for x in a] == \
        [(x["conversation_id"], x["decisao"]) for x in b]
    for r in run_queue(_csv_gw(), POLICY, fn):
        _confere_contrato(r)
    assert not contains_pii(json.dumps(a, ensure_ascii=False))


def test_cli_com_fallback_grava_o_json(tmp_path):
    saida = tmp_path / "results.json"
    assert run.main(["--out", str(saida), "--use-fallback"]) == 0
    dados = json.loads(saida.read_text(encoding="utf-8"))
    assert len(dados["resultados"]) == 65
    assert sum(dados["resumo"]["por_acao"].values()) == 65


# --- correção 1: rastreio parado, SLA respondido, troca sem produto ---

def test_rastreio_parado_real_abre_chamado_e_n01_n02_seguem_informando_status():
    gw = _csv_gw()
    fn = _fixo({c: _cl() for c in ("CV000011", "CV000033", "CV000015")})
    parado = run_conversation(gw, POLICY, fn, "CV000011")
    assert parado.decisao["acao"] == "abrir_chamado_transportadora"
    assert "parado há 5 dias úteis" in parado.decisao["motivo"]
    assert "previsão de entrega é" not in parado.resposta_cliente["texto"]
    for cid in ("CV000033", "CV000015"):
        assert run_conversation(gw, POLICY, fn, cid).decisao["acao"] == "informar_status"


@pytest.mark.parametrize("cid", ["CV000012", "CV000011"])
def test_conversa_ja_respondida_nao_tem_sla_negativo(cid):
    conv = _csv_gw().get_conversa(cid)
    assert conv["data_primeira_resposta"]
    r = run_conversation(_csv_gw(), POLICY, _fixo({cid: _cl()}), cid)
    assert r.sla_minutos_restantes is None and r.primeira_resposta_dada is True


def test_conversa_sem_resposta_tem_sla_e_flag_falsa():
    gw = FakeGateway(fila=[_conv("A1", canal="whatsapp")], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", "oi")]})
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl("elogio")}), "A1")
    assert r.primeira_resposta_dada is False and r.sla_minutos_restantes is not None


def test_troca_sem_produto_escolhido_fica_pendente():
    pedido = _pedido(status_entrega="entregue", data_entrega="2026-10-30")
    gw = FakeGateway(fila=[_conv("A1", "PED000001")], pedidos=[pedido], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", "quero trocar a fragrância")]})
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl("troca_fragrancia")}), "A1")
    assert r.decisao["ferramenta"] == "trocar_produto"
    assert "trocar_produto" in _tools(r, "pendente")
    assert "trocar_produto" not in [c.tool for c in gw.toolbox.calls]
    assert "qual produto" in r.resposta_cliente["texto"]


# --- Task 8: acoes_previas, log com tempo, marca e dados do pedido ---

def test_cupom_com_duvida_roda_validar_cupom_antes_de_acionar_pessoa():
    gw = FakeGateway(fila=[_conv("A1")], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", "meu cupom vale para esse kit?")]})
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl(
        "cupom_promocao", sinais=["duvida_elegibilidade_cupom"])}), "A1")
    assert r.decisao["acao"] == "validar_cupom;acionar_pessoa"
    ordem = [c["tool"] for c in r.calls if c["tool"] != "classificar_conversa"]
    assert ordem[:2] == ["validar_cupom", "acionar_pessoa"]
    assert "validar_cupom" in _tools(r, "pendente")  # sem código do cupom, fica pendente
    assert "acionar_pessoa" in _tools(r, "executada")
    _confere_contrato(r)


def test_cupom_sem_politica_aciona_pessoa_sem_validar():
    gw = FakeGateway(fila=[_conv("A1")], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", "tem desconto de black friday?")]})
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl(
        "cupom_promocao", sinais=["sem_politica_aplicavel"])}), "A1")
    assert r.decisao["acao"] == "acionar_pessoa"
    assert "validar_cupom" not in [c["tool"] for c in r.calls]


def test_log_tem_etapas_com_tempo_sem_texto_nem_ids():
    pedido = _pedido()
    gw = FakeGateway(fila=[_conv("A1", "PED000001")], pedidos=[pedido], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", f"cadê meu pedido? CPF {CPF}")]})
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl()}), "A1")
    etapas = [x["etapa"] for x in r.log]
    assert etapas == ["mascarar", "classificar", "consultar_pedido", "decidir", "executar"]
    for x in r.log:
        assert isinstance(x["ms"], float) and x["ms"] >= 0
        assert "PED000001" not in x["resultado"] and "A1" != x["resultado"]
        assert "cadê" not in x["resultado"] and not contains_pii(x["resultado"])
    assert r.log[1]["resultado"].startswith("onde_esta_pedido")
    assert r.log[3]["resultado"] == "informar_status"


def test_log_registra_a_falha_so_pelo_tipo():
    gw = FakeGateway(fila=[_conv("A1")], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", "oi")]})
    r = run_conversation(gw, POLICY, _fixo({"A1": RuntimeError(CPF)}), "A1")
    assert r.log[-1]["etapa"] == "falha"
    assert r.log[-1]["resultado"] == "RuntimeError"


def test_result_traz_marca_e_dados_do_pedido_sem_ids():
    pedido = _pedido()
    gw = FakeGateway(fila=[_conv("A1", "PED000001")], pedidos=[pedido], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", "cadê meu pedido?")]})
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl()}), "A1")
    assert r.marca == "Lumen"
    rotulos = {d["rotulo"]: d["valor"] for d in r.dados}
    assert rotulos["Status do pedido"] == "em_transito"
    assert rotulos["Valor do pedido"] == "R$ 150,00"
    assert "Data prometida" in rotulos
    assert all(isinstance(v, str) for v in rotulos.values())
    assert "PED000001" not in json.dumps(r.dados) and "C1" not in json.dumps(r.dados)


def test_cronometro_marca_ms_desde_a_etapa_anterior():
    tempos = iter([1.0, 1.25, 1.25, 2.0])
    log = []
    cron = run.Cronometro(log, relogio=lambda: next(tempos))
    cron.marca("a", "ok")
    cron.marca("b", "ok")
    cron.marca("c", "ok")
    assert [x["ms"] for x in log] == [250.0, 0.0, 750.0]


def test_cli_classifica_tambem_o_historico_dos_casos():
    from pipeline import cli
    ids = cli.historico_dos_casos()
    assert ids == ["CV000004", "CV000003", "CV000002", "CV000001", "CV000006"]


def test_cli_grava_o_export_publico(tmp_path):
    publico = tmp_path / "results.json"
    assert run.main(["--out", str(tmp_path / "priv.json"), "--use-fallback",
                     "--public", str(publico)]) == 0
    doc = json.loads(publico.read_text(encoding="utf-8"))
    assert doc["versao"] == 1 and doc["resumo"]["total"] == 65


def test_escalacao_com_sintoma_mantem_reacao_adversa():
    gw = FakeGateway(fila=[_conv("A1", "PED000001")], pedidos=[_pedido()], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", "fiquei com o rosto inchado")]})
    r = run_conversation(gw, POLICY, _fixo({"A1": Escalation("timeout")}), "A1")
    assert "orientar_suspensao_uso" in _tools(r)
    assert any(c["tool"] == "registrar_cosmetovigilancia" for c in r.calls)
    assert priority_key(r)[0] == 0


def test_cosmetovigilancia_com_prazo_vencido_e_avisada():
    gw = FakeGateway(fila=[_conv("A1", "PED000001", abertura="2026-10-30 09:00:00")],
                     pedidos=[_pedido()], clientes=[_cliente()],
                     mensagens={"A1": [_msg("A1", "deu alergia")]})
    r = run_conversation(gw, POLICY, _fixo({"A1": _cl("reacao_adversa")}), "A1")
    pend = next(c for c in r.calls if c["tool"] == "registrar_cosmetovigilancia")
    assert "PRAZO VENCIDO" in pend["motivo"]
