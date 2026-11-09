"""Perfil da fila aberta e baseline do historico (somente dados fornecidos)."""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "atendimento"


def ler(nome):
    with open(DATA / nome, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def custo_por_canal(politicas):
    """Custo por conversa (R$) por canal, lido de politicas.csv."""
    return {r["regra"]: float(r["valor"]) for r in politicas
            if r["secao"] == "custo_por_conversa_rs"}


def tags_das_categorias(politicas):
    return {r["valor"] for r in politicas
            if r["secao"] == "categorias" and r["regra"].endswith(".tag_equivalente") and r["valor"]}


def profile_queue(rows):
    return {
        "total": len(rows),
        "por_canal": dict(Counter(r["canal"] for r in rows)),
        "por_status": dict(Counter(r["status"] for r in rows)),
    }


def baseline(historico, tempos, csat, custos):
    por_canal = Counter(r["canal"] for r in historico)
    minutos = defaultdict(list)
    for t in tempos:
        if t.get("minutos_trabalhados"):
            minutos[t["canal"]].append(float(t["minutos_trabalhados"]))
    reabertas = sum(1 for r in historico if r["status"] == "reaberto")
    notas = [int(c["nota"]) for c in csat if c.get("nota")]
    return {
        "conversas_por_canal": dict(por_canal),
        "minutos_medios_por_canal": {c: round(sum(v) / len(v), 1) for c, v in minutos.items()},
        "custo_total_rs": round(sum(n * custos[c] for c, n in por_canal.items()), 2),
        "taxa_reabertura": reabertas / len(historico) if historico else 0.0,
        "csat_respondidas": len(notas),
        "csat_media": round(sum(notas) / len(notas), 2) if notas else None,
    }


def problemas(historico, politicas):
    validas = tags_das_categorias(politicas)
    sem_tag = sum(1 for r in historico if not r["tag_agente"])
    fora = Counter(r["tag_agente"] for r in historico
                   if r["tag_agente"] and r["tag_agente"] not in validas)
    sem_pedido = sum(1 for r in historico if not r["order_id"])
    return {"total": len(historico), "sem_tag": sem_tag,
            "tags_fora_das_categorias": dict(fora), "sem_pedido": sem_pedido,
            "status": dict(Counter(r["status"] for r in historico))}


if __name__ == "__main__":
    pol = ler("politicas.csv")
    hist = ler("historico_conversas.csv")
    saida = {"fila": profile_queue(ler("fila_aberta.csv")),
             "baseline": baseline(hist, ler("tempo_por_conversa.csv"),
                                  ler("avaliacoes_csat.csv"), custo_por_canal(pol)),
             "problemas": problemas(hist, pol)}
    sys.stdout.write(json.dumps(saida, ensure_ascii=False, indent=2) + "\n")
