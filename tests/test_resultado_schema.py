"""Contrato público v1: a amostra sintética (e o results.json real, se existir) valida contra
schemas/resultado_publico.schema.json, e o resumo bate com a contagem dos itens."""
import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

RAIZ = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((RAIZ / "schemas" / "resultado_publico.schema.json").read_text(encoding="utf-8"))
AMOSTRA = RAIZ / "web" / "data" / "results.sample.json"
REAL = RAIZ / "web" / "data" / "results.json"

ARQUIVOS = [AMOSTRA] + ([REAL] if REAL.exists() else [])


def _resumo(itens):
    s = {"total": len(itens), "automaticas": 0, "aprovacao": 0, "pessoa": 0, "supervisor": 0}
    for it in itens:
        s["automaticas" if it["destino"] == "automatico" else it["destino"]] += 1
    return s


def test_schema_e_valido():
    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda p: p.name)
def test_arquivo_valida_e_resumo_bate(arquivo):
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    erros = sorted(Draft202012Validator(SCHEMA).iter_errors(dados), key=lambda e: list(e.path))
    assert not erros, [f"{list(e.path)}: {e.message}" for e in erros]
    assert dados["resumo"] == _resumo(dados["itens"])


def test_schema_rejeita_campo_extra():
    dados = json.loads(AMOSTRA.read_text(encoding="utf-8"))
    dados["_aviso"] = "x"
    assert not Draft202012Validator(SCHEMA).is_valid(dados)


@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda p: p.name)
def test_sem_pii_nem_palavras_proibidas(arquivo):
    texto = arquivo.read_text(encoding="utf-8")
    assert not re.search(r"fraude|golpe", texto, re.I)
    assert not re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", texto), "parece CPF"
    assert not re.search(r"\(?\d{2}\)?\s?9?\d{4}-?\d{4}", texto), "parece telefone"
    assert not re.search(r"\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}", texto), "parece cartão"


def test_amostra_cobre_os_casos_da_demo():
    itens = json.loads(AMOSTRA.read_text(encoding="utf-8"))["itens"]
    acoes = {it["acao"] for it in itens}
    assert {"informar_status", "abrir_chamado_transportadora", "solicitar_foto", "solicitar_aprovacao",
            "acionar_pessoa", "sinalizar_suspeita", "negar_por_politica"} <= acoes
    sup = next(it for it in itens if it["destino"] == "supervisor")
    assert sup["evidencias"] and sup["resposta_cliente"] is None
    primeiro = min(itens, key=lambda it: it["prioridade"])
    assert primeiro["canal"] == "reclame_aqui"
