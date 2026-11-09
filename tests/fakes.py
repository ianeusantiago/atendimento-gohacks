"""FakeGateway em memória, sem CSV: prova que o pipeline só depende do Protocol Gateway."""
from datetime import datetime

from pipeline.asof import eventos_ate, pedido_as_of
from pipeline.policy import load_policy
from pipeline.tools import ToolBox


class FakeGateway:
    def __init__(self, fila=(), historico=(), mensagens=None, pedidos=(), clientes=(),
                 anexos=(), reenvios=None, pagamentos=None, estornos=None, itens=None,
                 policy=None, falhar_em=(), rastreio=None):
        self._fila = [dict(c) for c in fila]
        self._conversas = {c["conversation_id"]: dict(c) for c in [*fila, *historico]}
        self._mensagens = mensagens or {}
        self._pedidos = {p["order_id"]: dict(p) for p in pedidos}
        self._clientes = {c["customer_id"]: dict(c) for c in clientes}
        self._anexos = [dict(a) for a in anexos]
        self._reenvios, self._pagamentos = reenvios or {}, pagamentos or {}
        self._estornos, self._itens = estornos or {}, itens or {}
        self._rastreio = rastreio or {}
        self.toolbox = ToolBox("atendente", policy or load_policy())
        self.pedidos_consultados: list[str] = []
        self._falhar_em = set(falhar_em)  # ferramentas que levantam ao executar

    def get_conversa(self, conversation_id):
        c = self._conversas.get(conversation_id)
        return dict(c) if c else None

    def get_mensagens(self, conversation_id):
        return [dict(m) for m in self._mensagens.get(conversation_id, [])]

    def get_pedido(self, order_id, as_of: datetime | None = None):
        self.pedidos_consultados.append(order_id)
        p = self._pedidos.get(order_id)
        if p is None:
            return None
        return pedido_as_of(p, as_of) if as_of is not None else dict(p)

    def get_cliente(self, customer_id):
        c = self._clientes.get(customer_id)
        return dict(c) if c else None

    def get_anexos(self, conversation_id=None, order_id=None):
        return [dict(a) for a in self._anexos
                if (conversation_id is None or a["conversation_id"] == conversation_id)
                and (order_id is None or a["order_id"] == order_id)
                and (conversation_id or order_id)]

    def todos_anexos(self):
        return [dict(a) for a in self._anexos]

    def get_reenvios(self, order_id):
        return list(self._reenvios.get(order_id, []))

    def get_pagamentos(self, order_id):
        return list(self._pagamentos.get(order_id, []))

    def get_estornos(self, order_id):
        return list(self._estornos.get(order_id, []))

    def get_itens(self, order_id):
        return list(self._itens.get(order_id, []))

    def get_rastreio(self, order_id, as_of: datetime | None = None):
        eventos = [dict(e) for e in self._rastreio.get(order_id, [])]
        return eventos_ate(eventos, as_of, "data_hora_evento") if as_of is not None else eventos

    def fila(self):
        return [dict(c) for c in self._fila]

    def executar(self, ferramenta, **params):
        if ferramenta in self._falhar_em:
            raise ConnectionError("ambiente fora do ar: 123.456.789-09")
        return getattr(self.toolbox, ferramenta)(**params)


def copiar_do_csv(gw, conversation_ids, policy=None) -> FakeGateway:
    """FakeGateway com o MESMO conteúdo que `gw` tem para essas conversas (fila)."""
    fila = [c for c in gw.fila() if c["conversation_id"] in conversation_ids]
    pedidos, clientes = [], []
    oids = {c["order_id"] for c in fila if c["order_id"]}
    for oid in oids:
        pedidos.append(gw.get_pedido(oid))
    for c in fila:
        cliente = gw.get_cliente(c["customer_id"])
        if cliente:
            clientes.append(cliente)
    return FakeGateway(
        fila=fila, mensagens={c: gw.get_mensagens(c) for c in conversation_ids},
        pedidos=pedidos, clientes=clientes, anexos=gw.todos_anexos(),
        reenvios={o: gw.get_reenvios(o) for o in oids},
        pagamentos={o: gw.get_pagamentos(o) for o in oids},
        estornos={o: gw.get_estornos(o) for o in oids},
        itens={o: gw.get_itens(o) for o in oids},
        rastreio={o: gw.get_rastreio(o) for o in oids}, policy=policy)
