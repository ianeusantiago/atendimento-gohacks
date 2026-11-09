"""Export público (contrato v1, schemas/resultado_publico.schema.json) para web/data/results.json.

Só campos derivados: alias CONV-001... na ordem de prioridade (nenhum conversation_id,
customer_id ou order_id), canal, grupo da marca, categoria, ação, destino, motivo e regra
gerados pelo código, fatos do pedido (CaseResult.dados), evidências dos anexos, a resposta
montada por template (respostas.py) e o log com tempos. Nunca texto livre do cliente.

Ids que aparecem dentro de textos gerados pelo código (motivo, resposta, evidência) viram
pseudônimos: conversa da fila -> seu alias; outra conversa -> HIST-001; pedido -> PED-001;
cliente -> C-001;
qualquer outro código interno (reenvio, transação, anexo) -> REF-001.

Guarda: levanta PIILeak se mask.contains_pii acusar qualquer string exportada ou se sobrar um
id original; valida contra o JSON Schema antes de gravar; resumo = summarize(itens).
"""
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from pipeline.config import NOW
from pipeline import data as _data
from pipeline.deadlines import MARCA_MODAVIVA
from pipeline.mask import Pseudonymizer, contains_pii

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "resultado_publico.schema.json"
VERSAO = 1
DESTINOS = {"solicitar_aprovacao": "aprovacao", "acionar_pessoa": "pessoa",
            "sinalizar_suspeita": "supervisor"}
# Ferramentas de bastidor que não entram em acoes_secundarias.
FORA_DAS_SECUNDARIAS = {"classificar_conversa", "responder_cliente"}
SEM_CATEGORIA = "nao_classificada"

_CONVERSA = re.compile(r"\bCV\d{6}\b")
_PEDIDO = re.compile(r"\bPED\d{6}(?:-R\d+)?\b")
_CLIENTE = re.compile(r"\bCH\d{6}\b")
_OUTRO_CODIGO =re.compile(r"\b[A-Z]{2,4}\d{5,}\b")
# O que nunca pode sobrar no arquivo (conversa, pedido, cliente).
ID_ORIGINAL = re.compile(r"CV\d{6}|PED\d+|CH\d{6}")


class PIILeak(ValueError):
    """Um valor do export público contém PII ou um id original."""


def summarize(itens: list[dict]) -> dict:
    """Mesma contagem de web/render.js summarize()."""
    s = {"total": len(itens), "automaticas": 0, "aprovacao": 0, "pessoa": 0, "supervisor": 0}
    for it in itens:
        s["automaticas" if it["destino"] == "automatico" else it["destino"]] += 1
    return s


def destino(ferramenta: str | None) -> str:
    return DESTINOS.get(ferramenta, "automatico")


def marca_grupo(marca: str) -> str:
    # parametros.md: Modaviva e as marcas Belleza (Aurora, Brisa, Lótus, Alvorada, ...).
    return "Modaviva" if marca == MARCA_MODAVIVA else "Belleza"


class _Anonimizador:
    def __init__(self, aliases: dict[str, str]) -> None:
        self._aliases = aliases
        self._hist, self._ped = Pseudonymizer("HIST"), Pseudonymizer("PED")
        self._ref, self._cli = Pseudonymizer("REF"), Pseudonymizer()

    def __call__(self, texto: str | None) -> str | None:
        if texto is None:
            return None
        texto = _PEDIDO.sub(lambda m: self._ped.alias(m.group()), texto)
        texto = _CLIENTE.sub(lambda m: self._cli.alias(m.group()), texto)
        texto = _CONVERSA.sub(lambda m: self._aliases.get(m.group())
                              or self._hist.alias(m.group()), texto)
        return _OUTRO_CODIGO.sub(lambda m: self._ref.alias(m.group()), texto)


def _get(r, campo):
    return r[campo] if isinstance(r, dict) else getattr(r, campo)


def _secundarias(ferramenta: str, decisao: dict, calls: list[dict]) -> list[str]:
    saida = []
    if ferramenta == "solicitar_aprovacao" and decisao["params"].get("acao"):
        saida.append(decisao["params"]["acao"])
    for c in calls:
        t = c["tool"]
        if t not in FORA_DAS_SECUNDARIAS and t != ferramenta and t not in saida:
            saida.append(t)
    return saida


def _item(r, alias: str, prioridade: int, anon: _Anonimizador) -> dict:
    cl, decisao = _get(r, "classificacao"), _get(r, "decisao")
    ferramenta = decisao.get("ferramenta") or decisao["acao"]
    resposta = _get(r, "resposta_cliente")
    return {
        "alias": alias,
        "canal": _get(r, "canal"),
        "marca_grupo": marca_grupo(_get(r, "marca")),
        "prioridade": prioridade,
        "categoria": cl.get("categoria") or SEM_CATEGORIA,
        "categoria_secundaria": cl.get("categoria_secundaria"),
        "acao": ferramenta,
        "destino": destino(ferramenta),
        "acoes_secundarias": _secundarias(ferramenta, decisao, _get(r, "calls")),
        "motivo": anon(decisao["motivo"]),
        "regra": decisao["regra"],
        "dados": [{"rotulo": d["rotulo"], "valor": anon(d["valor"])} for d in _get(r, "dados")],
        "evidencias": [{"tipo": e["kind"], "detalhe": anon(e["detail"])}
                       for e in _get(r, "evidencias")],
        "resposta_cliente": anon(resposta["texto"]) if resposta else None,
        "log": [{"etapa": x["etapa"], "resultado": anon(x["resultado"]), "ms": x["ms"]}
                for x in _get(r, "log")],
    }


def _strings(valor):
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _strings(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from _strings(v)


def conferir(doc: dict) -> None:
    """PIILeak se alguma string tem PII ou id original; ValidationError se fora do schema."""
    for s in _strings(doc):
        if contains_pii(s):
            raise PIILeak("valor exportado contém PII (CPF, cartão ou telefone)")
        if ID_ORIGINAL.search(s):
            raise PIILeak("valor exportado contém um id original")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(doc)
    if doc["resumo"] != summarize(doc["itens"]):
        raise ValueError("resumo diferente de summarize(itens)")


def tempo_referencia() -> dict | None:
    """Média histórica de minutos trabalhados por conversa (tempo_por_conversa.csv), ou None."""
    try:
        linhas = _data.read_csv("tempo_por_conversa.csv")
    except FileNotFoundError:
        return None
    mins = [float(r["minutos_trabalhados"]) for r in linhas if (r.get("minutos_trabalhados") or "").strip()]
    if not mins:
        return None
    return {"media_minutos": round(sum(mins) / len(mins), 1), "conversas": len(mins),
            "fonte": "tempo_por_conversa.csv (minutos_trabalhados)"}


def montar(results) -> dict:
    ordenados = sorted(results, key=lambda r: _get(r, "prioridade"))
    pseudo = Pseudonymizer("CONV")
    aliases = {_get(r, "conversation_id"): pseudo.alias(_get(r, "conversation_id"))
               for r in ordenados}
    anon = _Anonimizador(aliases)
    itens = [_item(r, aliases[_get(r, "conversation_id")], i, anon)
             for i, r in enumerate(ordenados, 1)]
    doc = {"versao": VERSAO, "gerado_em": NOW.strftime("%Y-%m-%d %H:%M"),
           "resumo": summarize(itens), "itens": itens}
    ref = tempo_referencia()
    if ref:
        doc["tempo_referencia"] = ref
    return doc


def export_public(results, out_path: Path) -> None:
    doc = montar(results)
    conferir(doc)  # antes de gravar: nada sai se falhar
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
