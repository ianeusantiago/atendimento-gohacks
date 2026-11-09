"""Gateway: único ponto de acesso a dados e ferramentas.

run.py, case_builder.py, decide.py e evidence.py dependem só deste Protocol, nunca de Dataset
nem de caminhos de CSV. CsvGateway é a implementação local; a implementação remota (API do
ambiente do evento, a confirmar) só será escrita quando o formato for conhecido.

Extensões ao Protocol listado no plano (Task 7):
- get_pedido(order_id, as_of=None): com as_of devolve o pedido como estava naquela data
  (pipeline/asof.pedido_as_of); sem as_of, o retrato de 02/11.
- get_reenvios, get_pagamentos, get_estornos, get_itens: o contexto do pedido que decide.py
  usa (pipeline/context_rules.py). O corte por data é do case_builder (asof.eventos_ate).
- get_rastreio(order_id, as_of=None): eventos do portal da transportadora do pedido
  (rastreio_portais_transportadoras.csv, por pedido_ref), em ordem de data_hora_evento; com
  as_of, só os eventos até essa data (asof.eventos_ate).
"""
from datetime import datetime
from typing import Protocol, runtime_checkable

from pipeline.asof import eventos_ate, pedido_as_of
from pipeline.data import Dataset


@runtime_checkable
class Gateway(Protocol):
    def get_conversa(self, conversation_id: str) -> dict | None: ...
    def get_mensagens(self, conversation_id: str) -> list[dict]: ...
    def get_pedido(self, order_id: str, as_of: datetime | None = None) -> dict | None: ...
    def get_cliente(self, customer_id: str) -> dict | None: ...
    def get_anexos(self, conversation_id: str | None = None,
                   order_id: str | None = None) -> list[dict]: ...
    def todos_anexos(self) -> list[dict]: ...
    def get_reenvios(self, order_id: str) -> list[dict]: ...
    def get_pagamentos(self, order_id: str) -> list[dict]: ...
    def get_estornos(self, order_id: str) -> list[dict]: ...
    def get_itens(self, order_id: str) -> list[dict]: ...
    def get_rastreio(self, order_id: str, as_of: datetime | None = None) -> list[dict]: ...
    def fila(self) -> list[dict]: ...
    def executar(self, ferramenta: str, **params) -> dict: ...


class CsvGateway:
    """Gateway sobre os CSVs carregados em Dataset. toolbox pode ser None para uso só leitura
    (testes que montam Case); executar() exige um ToolBox."""

    def __init__(self, dataset: Dataset, toolbox=None) -> None:
        self._ds = dataset
        self.toolbox = toolbox
        self._fila = {c["conversation_id"]: c for c in dataset.fila}

    def get_conversa(self, conversation_id: str) -> dict | None:
        conv = self._fila.get(conversation_id) or self._ds.historico.get(conversation_id)
        return dict(conv) if conv else None

    def get_mensagens(self, conversation_id: str) -> list[dict]:
        return [dict(m) for m in self._ds.mensagens.get(conversation_id, [])]

    def get_pedido(self, order_id: str, as_of: datetime | None = None) -> dict | None:
        pedido = self._ds.pedidos.get(order_id)
        if pedido is None:
            return None
        return pedido_as_of(pedido, as_of) if as_of is not None else dict(pedido)

    def get_cliente(self, customer_id: str) -> dict | None:
        cliente = self._ds.clientes.get(customer_id)
        return dict(cliente) if cliente else None

    def get_anexos(self, conversation_id: str | None = None,
                   order_id: str | None = None) -> list[dict]:
        if conversation_id is not None:
            rows = self._ds.anexos.get(conversation_id, [])
            if order_id is not None:
                rows = [a for a in rows if a["order_id"] == order_id]
        elif order_id is not None:
            rows = self._ds.anexos_por_pedido.get(order_id, [])
        else:
            rows = []
        return [dict(a) for a in rows]

    def todos_anexos(self) -> list[dict]:
        return list(self._ds.todos_anexos)

    def get_reenvios(self, order_id: str) -> list[dict]:
        return list(self._ds.reenvios.get(order_id, []))

    def get_pagamentos(self, order_id: str) -> list[dict]:
        return list(self._ds.pagamentos.get(order_id, []))

    def get_estornos(self, order_id: str) -> list[dict]:
        return list(self._ds.estornos.get(order_id, []))

    def get_itens(self, order_id: str) -> list[dict]:
        return list(self._ds.itens_pedido.get(order_id, []))

    def get_rastreio(self, order_id: str, as_of: datetime | None = None) -> list[dict]:
        eventos = [dict(e) for e in self._ds.rastreio.get(order_id, [])]
        return eventos_ate(eventos, as_of, "data_hora_evento") if as_of is not None else eventos

    def fila(self) -> list[dict]:
        return [dict(c) for c in self._ds.fila]

    def executar(self, ferramenta: str, **params) -> dict:
        if self.toolbox is None:
            raise RuntimeError("CsvGateway sem ToolBox: executar() indisponível")
        return getattr(self.toolbox, ferramenta)(**params)
