"""Leitura dos CSVs de data/atendimento/ (dados fora do git)."""
import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "atendimento"


def read_csv(name: str) -> list[dict[str, str]]:
    with open(DATA_DIR / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class Dataset:
    fila: list[dict]
    historico: dict[str, dict]
    pedidos: dict[str, dict]
    clientes: dict[str, dict]
    mensagens: dict[str, list[dict]]
    anexos: dict[str, list[dict]]  # por conversation_id
    todos_anexos: list[dict]
    # Por order_id (linhas no retrato de 02/11; o corte por data é de pipeline/asof.py).
    anexos_por_pedido: dict[str, list[dict]]
    reenvios: dict[str, list[dict]]  # trocas_reenvios.csv (order_id_original)
    pagamentos: dict[str, list[dict]]  # pagamentos_gateway.csv
    estornos: dict[str, list[dict]]  # estornos.csv
    itens_pedido: dict[str, list[dict]]  # itens_pedido.csv (brinde da campanha com preço 0)
    # rastreio_portais_transportadoras.csv por pedido_ref, em ordem de data_hora_evento.
    rastreio: dict[str, list[dict]] = field(default_factory=dict)


def _por(rows: list[dict], chave: str) -> dict[str, dict]:
    return {r[chave]: r for r in rows}


def _agrupar(rows: list[dict], chave: str) -> dict[str, list[dict]]:
    grupos: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        grupos[r[chave]].append(r)
    return dict(grupos)


def _ordenar(rows: list[dict], campo: str) -> list[dict]:
    return sorted(rows, key=lambda r: r[campo])  # ISO: ordem de texto = ordem de tempo


def load_dataset() -> Dataset:
    mensagens = _agrupar(read_csv("historico_mensagens.csv"), "conversation_id")
    for msgs in mensagens.values():
        msgs.sort(key=lambda m: m["timestamp"])  # ISO: ordem de texto = ordem de tempo
    todos_anexos = read_csv("anexos_conversas.csv")
    return Dataset(
        fila=read_csv("fila_aberta.csv"),
        historico=_por(read_csv("historico_conversas.csv"), "conversation_id"),
        pedidos=_por(read_csv("pedidos.csv"), "order_id"),
        clientes=_por(read_csv("clientes.csv"), "customer_id"),
        mensagens=mensagens,
        anexos=_agrupar(todos_anexos, "conversation_id"),
        todos_anexos=todos_anexos,
        anexos_por_pedido=_agrupar(todos_anexos, "order_id"),
        reenvios=_agrupar(_ordenar(read_csv("trocas_reenvios.csv"), "data_solicitacao"),
                          "order_id_original"),
        pagamentos=_agrupar(_ordenar(read_csv("pagamentos_gateway.csv"), "data_hora_criacao"),
                            "order_id"),
        estornos=_agrupar(_ordenar(read_csv("estornos.csv"), "data_hora_solicitacao"),
                          "order_id"),
        itens_pedido=_agrupar(read_csv("itens_pedido.csv"), "order_id"),
        rastreio=_agrupar(_ordenar(read_csv("rastreio_portais_transportadoras.csv"),
                                   "data_hora_evento"), "pedido_ref"),
    )
