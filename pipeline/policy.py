"""Regras de negocio lidas de politicas.csv (secao,regra,valor) no carregamento."""
from dataclasses import dataclass, field
from datetime import date

from pipeline.data import read_csv

# Categorias cujo prazo "7 dias do recebimento" e o prazo_dias da politica.
# troca_fragrancia tem prazo proprio (30) e fica em categorias.
CATEGORIAS_PRAZO = ("item_faltante", "avaria_vazamento", "erro_personalizacao",
                    "arrependimento_cancelamento")


@dataclass
class Policy:
    limite_reenvio: float
    limite_reembolso: float
    limite_troca: float
    prazo_dias: int
    preparo: dict[str, int]
    sla: dict[tuple[str, str], int]
    regiao_por_uf: dict[str, str]
    feriados: set[date]
    categorias: dict[str, dict]
    tags: list[str]
    # Todas as seções como texto (secao -> regra -> valor), para regras sem campo próprio
    # (sla_primeira_resposta, horario_atendimento_humano, reclamacao_suspeita...).
    regras: dict[str, dict[str, str]] = field(default_factory=dict)


def _lista(valor: str) -> list[str]:
    return [v.strip() for v in valor.split(";") if v.strip()]


def _valor(campo: str, valor: str):
    """Converte o texto da celula: bool, int, float, lista com ';' ou texto."""
    if valor in ("True", "False"):
        return valor == "True"
    for tipo in (int, float):
        try:
            return tipo(valor)
        except ValueError:
            pass
    if campo != "regra" and ";" in valor:
        return _lista(valor)
    return valor


def load_policy() -> Policy:
    rows = read_csv("politicas.csv")
    secoes: dict[str, dict[str, str]] = {}
    for r in rows:
        secoes.setdefault(r["secao"], {})[r["regra"]] = r["valor"]

    limites = secoes["limites_por_papel"]
    prazos = secoes["prazos_entrega"]

    preparo, sla, regiao = {}, {}, {}
    for regra, valor in prazos.items():
        if regra.startswith("preparo_dias_uteis."):
            preparo[regra.split(".", 1)[1]] = int(valor)
        elif regra.startswith("sla_transportadora_dias_uteis."):
            # Transportadora pode ter espaco e acento; a regiao e o ultimo trecho.
            transp, reg = regra.split(".", 1)[1].rsplit(".", 1)
            sla[(transp, reg)] = int(valor)
        elif regra.startswith("regiao_por_uf."):
            regiao[regra.split(".", 1)[1]] = valor

    categorias: dict[str, dict] = {}
    for regra, valor in secoes["categorias"].items():
        nome, campo = regra.split(".", 1)
        categorias.setdefault(nome, {})[campo] = _valor(campo, valor)

    prazos_cat = {categorias[c]["prazo_dias_corridos_do_recebimento"]
                  for c in CATEGORIAS_PRAZO}
    if len(prazos_cat) != 1:
        raise ValueError(f"prazos divergentes em politicas.csv: {sorted(prazos_cat)}")

    return Policy(
        limite_reenvio=float(limites["atendente.reenvio_ou_reimpressao_max_rs"]),
        limite_reembolso=float(limites["atendente.reembolso_max_rs"]),
        limite_troca=float(limites["atendente.troca_max_rs"]),
        prazo_dias=prazos_cat.pop(),
        preparo=preparo,
        sla=sla,
        regiao_por_uf=regiao,
        feriados={date.fromisoformat(d) for d in _lista(prazos["feriados_nacionais"])},
        categorias=categorias,
        tags=_lista(secoes["tags_agente"]["tags_agente"]),
        regras=secoes,
    )
