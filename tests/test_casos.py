import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data" / "atendimento"


def ler(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


CASOS = ler(ROOT / "evals" / "casos.csv")
HIST = {x["conversation_id"] for x in ler(D / "historico_conversas.csv")}
FILA = {x["conversation_id"] for x in ler(D / "fila_aberta.csv")}
FERRAMENTAS = {x["ferramenta"] for x in ler(D / "ferramentas.csv")}
POLITICAS = ler(D / "politicas.csv")
REGRAS = {x["secao"] for x in POLITICAS} | {x["regra"].split(".")[0] for x in POLITICAS}
ANEXOS = {x["conversation_id"] for x in ler(D / "anexos_conversas.csv")}


def test_casos_shape():
    assert len(CASOS) == 15
    assert Counter(c["tipo"] for c in CASOS) == {"normal": 7, "dificil": 5, "ambiguo": 2, "malicioso": 1}
    assert len({c["caso_id"] for c in CASOS}) == 15
    for c in CASOS:
        assert c["conversation_id"] in HIST | FILA
        assert c["regra_politicas"] in REGRAS
        acoes = c["acao_esperada"].split(";")
        assert acoes and all(a in FERRAMENTAS for a in acoes)
        assert c["categoria_esperada"]


def test_origem_coerente_com_os_dados():
    for c in CASOS:
        fonte = FILA if c["origem"] == "fila" else HIST
        assert c["origem"] in ("fila", "historico")
        assert c["conversation_id"] in fonte


def test_caso_de_foto_e_historico_com_anexo():
    fotos = [c for c in CASOS if "sinalizar_suspeita" in c["acao_esperada"].split(";")]
    assert fotos
    for c in fotos:
        assert c["origem"] == "historico"
        assert c["conversation_id"] in ANEXOS
