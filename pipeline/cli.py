"""CLI da fila: py -m pipeline.run --out out/results.json [--use-fallback] [--public PATH].

--public grava também o export público (contrato v1, pipeline/export.py), ex.:
web/data/results.json.

Sem --use-fallback: classifica pelo AI proxy (sequencial, com intervalo mínimo entre chamadas
para respeitar o limite compartilhado), salva as classificações válidas em
fallback/classificacoes.json (só id e campos derivados) e mostra o uso de tokens. Além da fila,
classifica as conversas do histórico usadas em evals/casos.csv, para a avaliação
(py -m evals.run_evals) ler a mesma classificação salva.
Com --use-fallback: lê esse arquivo e não chama o proxy.
Imprime só contagens: nunca texto de mensagem, CPF, telefone, cartão ou o token.
"""
import argparse
import csv
import json
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from pipeline import config, llm
from pipeline.models import Classificacao, Escalation

ROOT = Path(__file__).resolve().parent.parent
FALLBACK = ROOT / "fallback" / "classificacoes.json"
CASOS = ROOT / "evals" / "casos.csv"
CAMPOS_FALLBACK = ("categoria", "categoria_secundaria", "order_id", "sinais_risco", "confianca")
# Proxy compartilhado (~250 req/min): no máximo 200/min a partir deste processo.
INTERVALO_MIN_S = 0.3


def historico_dos_casos(path: Path = CASOS) -> list[str]:
    """conversation_id dos casos de avaliação que vêm do histórico (fora da fila)."""
    with open(path, encoding="utf-8", newline="") as f:
        return [c["conversation_id"] for c in csv.DictReader(f) if c["origem"] == "historico"]


def classify_from_fallback(path: Path = FALLBACK):
    dados = json.loads(Path(path).read_text(encoding="utf-8"))

    def fn(texto: str, conversation_id: str):
        cl = dados.get(conversation_id)
        if cl is None:
            return Escalation("classificacao salva ausente no fallback")
        return Classificacao(**cl)
    return fn


class _ContadorDeTokens:
    """Envolve o client OpenAI: soma prompt/completion tokens e espaça as chamadas."""

    def __init__(self, client, intervalo: float = INTERVALO_MIN_S) -> None:
        self._client, self._intervalo, self._ultima = client, intervalo, 0.0
        self.prompt = self.completion = self.chamadas = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        espera = self._intervalo - (time.monotonic() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        self._ultima = time.monotonic()
        self.chamadas += 1
        resp = self._client.chat.completions.create(**kwargs)
        usage = getattr(resp, "usage", None)
        self.prompt += getattr(usage, "prompt_tokens", 0) or 0
        self.completion += getattr(usage, "completion_tokens", 0) or 0
        return resp


class ClassificadorProxy:
    """classify_fn real: llm.classify com contador de tokens; guarda as classificações."""

    def __init__(self) -> None:
        self.salvas: dict[str, dict] = {}
        try:
            client, _ = llm._build_client()
        except config.MissingToken:
            client = None
        self.contador = _ContadorDeTokens(client) if client else None

    def __call__(self, texto: str, conversation_id: str):
        if self.contador is None:
            return Escalation("token do AI proxy ausente")
        r = llm.classify(texto, client=self.contador)
        if isinstance(r, Classificacao):
            self.salvas[conversation_id] = {k: asdict(r)[k] for k in CAMPOS_FALLBACK}
        return r


def resumo(resultados) -> dict:
    por_acao = Counter(r.decisao["acao"] for r in resultados)
    return {
        "total": len(resultados),
        "por_acao": dict(sorted(por_acao.items())),
        "para_pessoa": sum(r.decisao["ferramenta"] == "acionar_pessoa" for r in resultados),
        "escaladas_pelo_classificador": sum("escalation" in r.classificacao for r in resultados),
        "falhas_isoladas": sum(r.decisao["regra"] == "falha_pipeline" for r in resultados),
        "chamadas_pendentes": sum(c["status"] == "pendente" for r in resultados
                                  for c in r.calls),
    }


def main(argv=None) -> int:
    from pipeline.data import load_dataset
    from pipeline.gateway import CsvGateway
    from pipeline.policy import load_policy
    from pipeline.run import run_conversation, run_queue
    from pipeline.tools import ToolBox

    parser = argparse.ArgumentParser(prog="py -m pipeline.run")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--use-fallback", action="store_true",
                        help="usa fallback/classificacoes.json em vez do proxy")
    parser.add_argument("--fallback", type=Path, default=FALLBACK)
    parser.add_argument("--public", type=Path, default=None,
                        help="grava o export público (contrato v1) neste caminho")
    args = parser.parse_args(argv)

    policy = load_policy()
    gw = CsvGateway(load_dataset(), ToolBox("atendente", policy))
    proxy = None
    if args.use_fallback:
        classify_fn, fonte = classify_from_fallback(args.fallback), "fallback"
    else:
        proxy = ClassificadorProxy()
        classify_fn, fonte = proxy, f"proxy ({config.model_name()}, prompt {llm.PROMPT_VERSION})"

    resultados = run_queue(gw, policy, classify_fn)
    info = resumo(resultados)
    if proxy is not None:
        for cid in historico_dos_casos():  # só para salvar a classificação usada nos evals
            run_conversation(gw, policy, proxy, cid)
        c = proxy.contador
        info["tokens"] = {"chamadas": c.chamadas if c else 0, "prompt": c.prompt if c else 0,
                          "completion": c.completion if c else 0}
        if proxy.salvas:
            args.fallback.parent.mkdir(parents=True, exist_ok=True)
            args.fallback.write_text(json.dumps(dict(sorted(proxy.salvas.items())),
                                                ensure_ascii=False, indent=1) + "\n",
                                     encoding="utf-8")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"fonte_classificacao": fonte, "resumo": info,
                                    "resultados": [asdict(r) for r in resultados]},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    if args.public:
        from pipeline.export import export_public, summarize
        export_public(resultados, args.public)
        publico = json.loads(args.public.read_text(encoding="utf-8"))
        print("export público:", args.public.as_posix(), json.dumps(summarize(publico["itens"])))
    print(f"fonte: {fonte}")
    print(json.dumps(info, ensure_ascii=False, indent=1))
    return 0
