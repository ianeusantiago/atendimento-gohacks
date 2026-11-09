import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import importlib.util  # noqa: E402

# "profile" colide com um modulo da stdlib: carrega pelo caminho.
_spec = importlib.util.spec_from_file_location("atend_profile", ROOT / "scripts" / "profile.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
profile_queue, baseline, custo_por_canal = _mod.profile_queue, _mod.baseline, _mod.custo_por_canal

D = ROOT / "data" / "atendimento"


def ler(nome):
    with open(D / nome, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_queue_counts():
    q = profile_queue(ler("fila_aberta.csv"))
    assert q["total"] == 65
    assert q["por_canal"] == {"reclame_aqui": 24, "email": 22, "whatsapp": 19}
    assert q["por_status"] == {"aberto": 59, "pendente": 6}


def test_custo_vem_de_politicas():
    assert custo_por_canal(ler("politicas.csv")) == {
        "whatsapp": 4.8, "email": 7.2, "reclame_aqui": 42.0}


def test_baseline_pequeno():
    hist = [{"conversation_id": "a", "canal": "email", "status": "reaberto"},
            {"conversation_id": "b", "canal": "email", "status": "resolvido"}]
    tempos = [{"conversation_id": "a", "canal": "email", "minutos_trabalhados": "10"},
              {"conversation_id": "b", "canal": "email", "minutos_trabalhados": "20"}]
    b = baseline(hist, tempos, [], {"email": 7.2})
    assert b["conversas_por_canal"] == {"email": 2}
    assert b["minutos_medios_por_canal"] == {"email": 15.0}
    assert b["custo_total_rs"] == 14.4
    assert b["taxa_reabertura"] == 0.5
