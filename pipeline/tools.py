"""ToolBox: as ferramentas de ferramentas.csv, com papéis e limites lidos do próprio CSV.

Cada método tem o mesmo nome e os mesmos parâmetros da ferramenta, na mesma ordem e só por
nome (obrigatórios = marcados com * no CSV, sem valor padrão). A chamada é validada (papel, parâmetros obrigatórios, valor sem aprovação) antes de
ser registrada em ToolBox.calls; chamada negada levanta exceção e não fica registrada.
Aqui não há efeito externo: o registro é a execução simulada. Só ferramentas usadas pelo
pipeline (ou exigidas nos testes) têm método.
"""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

from pipeline.config import NOW
from pipeline.data import read_csv
from pipeline.decide import LIMITE
from pipeline.policy import Policy


class NotPermitted(PermissionError):
    """O papel não está em papeis_permitidos da ferramenta."""


class LimitExceeded(PermissionError):
    """valor acima de valor_max_sem_aprovacao_rs sem aprovacao_id."""


class MissingParam(ValueError):
    """Parâmetro obrigatório (* em ferramentas.csv) ausente ou vazio."""


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    papeis: frozenset[str]
    obrigatorios: tuple[str, ...]
    parametros: tuple[str, ...]
    limites: dict = field(hash=False)

    @property
    def valor_max(self) -> float | None:
        valor = self.limites.get("valor_max_sem_aprovacao_rs")
        return float(valor) if valor is not None else None


def _lista(valor: str) -> list[str]:
    return [v.strip() for v in valor.split(";") if v.strip()]


def load_ferramentas() -> dict[str, Ferramenta]:
    ferramentas = {}
    for r in read_csv("ferramentas.csv"):
        params = _lista(r["parametros"])
        ferramentas[r["ferramenta"]] = Ferramenta(
            nome=r["ferramenta"], papeis=frozenset(_lista(r["papeis_permitidos"])),
            obrigatorios=tuple(p.rstrip("*") for p in params if p.endswith("*")),
            parametros=tuple(p.rstrip("*") for p in params),
            limites=json.loads(r["limites"] or "{}"))
    return ferramentas


FERRAMENTAS = load_ferramentas()
PAPEIS = frozenset().union(*(f.papeis for f in FERRAMENTAS.values()))
# Áreas de acionar_pessoa (ferramentas.csv, descrição: "supervisão, logística, qualidade,
# produção, jurídico, comercial"), sem acento como no resto do código.
AREAS = frozenset({"supervisao", "logistica", "qualidade", "producao", "juridico", "comercial"})


def permitido(papel: str, ferramenta: str) -> bool:
    return papel in FERRAMENTAS[ferramenta].papeis


@dataclass
class Call:
    tool: str
    params: dict
    role: str
    ts: datetime

    def as_dict(self) -> dict:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        return d


def _conferir_limites(policy: Policy) -> None:
    """ferramentas.csv e politicas.csv trazem o mesmo limite em dois lugares; divergência
    é erro de dados e para o pipeline (não escolhemos um dos dois em silêncio)."""
    for nome, atributo in LIMITE.items():
        if FERRAMENTAS[nome].valor_max != getattr(policy, atributo):
            raise ValueError(f"limite divergente entre ferramentas.csv e politicas.csv: {nome}")


class ToolBox:
    def __init__(self, role: str, policy: Policy, clock=lambda: NOW,
                 aprovadas: set[str] | None = None) -> None:
        # Ids aprovados por aprovar_acao (compartilhe o mesmo set entre o ToolBox do
        # supervisor e o do atendente). Id inventado não libera valor acima do limite.
        self.aprovadas: set[str] = aprovadas if aprovadas is not None else set()
        if role not in PAPEIS:
            raise ValueError(f"papel desconhecido: {role}")
        _conferir_limites(policy)
        self.role = role
        self.policy = policy
        self.calls: list[Call] = []
        self._clock = clock  # "agora" do ambiente simulado (determinístico)

    def _call(self, ferramenta: str, **params) -> dict:
        spec = FERRAMENTAS[ferramenta]
        if not permitido(self.role, ferramenta):
            raise NotPermitted(f"{self.role} não pode usar {ferramenta}")
        params = {k: v for k, v in params.items() if v is not None}
        faltando = [p for p in spec.obrigatorios if params.get(p) in (None, "", [])]
        if faltando:
            raise MissingParam(f"{ferramenta}: faltam {', '.join(faltando)}")
        if ferramenta == "acionar_pessoa" and params["area"] not in AREAS:
            raise MissingParam(f"acionar_pessoa: área fora de ferramentas.csv ({params['area']})")
        limite = spec.valor_max
        if limite is not None and float(params["valor"]) > limite \
                and params.get("aprovacao_id") not in self.aprovadas:
            raise LimitExceeded(f"{ferramenta}: valor acima de R$ {limite:.2f} sem aprovação")
        call = Call(ferramenta, params, self.role, self._clock())
        self.calls.append(call)
        return call.as_dict()

    # --- atendimento ao cliente ---
    def responder_cliente(self, *, conversation_id, texto):
        return self._call("responder_cliente", conversation_id=conversation_id, texto=texto)

    def classificar_conversa(self, *, conversation_id, categoria, categoria_secundaria=None):
        return self._call("classificar_conversa", conversation_id=conversation_id,
                          categoria=categoria, categoria_secundaria=categoria_secundaria)

    def solicitar_foto(self, *, conversation_id, do_que=None):
        return self._call("solicitar_foto", conversation_id=conversation_id, do_que=do_que)

    def informar_status(self, *, conversation_id, order_id):
        return self._call("informar_status", conversation_id=conversation_id, order_id=order_id)

    def responder_duvida(self, *, conversation_id, sku=None):
        return self._call("responder_duvida", conversation_id=conversation_id, sku=sku)

    def agradecer(self, *, conversation_id):
        return self._call("agradecer", conversation_id=conversation_id)

    def encerrar_conversa(self, *, conversation_id, motivo=None):
        return self._call("encerrar_conversa", conversation_id=conversation_id, motivo=motivo)

    def negar_por_politica(self, *, conversation_id, regra):
        return self._call("negar_por_politica", conversation_id=conversation_id, regra=regra)

    def orientar_suspensao_uso(self, *, conversation_id):
        return self._call("orientar_suspensao_uso", conversation_id=conversation_id)

    # --- pedido, logística e pagamento ---
    def abrir_chamado_transportadora(self, *, order_id, motivo):
        return self._call("abrir_chamado_transportadora", order_id=order_id, motivo=motivo)

    def cancelar_pedido(self, *, order_id, motivo=None):
        return self._call("cancelar_pedido", order_id=order_id, motivo=motivo)

    def alterar_endereco(self, *, order_id, novo_endereco):
        return self._call("alterar_endereco", order_id=order_id, novo_endereco=novo_endereco)

    def verificar_pagamento(self, *, order_id):
        return self._call("verificar_pagamento", order_id=order_id)

    def validar_cupom(self, *, codigo, order_id=None):
        return self._call("validar_cupom", codigo=codigo, order_id=order_id)

    # --- ações com dinheiro (limite de ferramentas.csv) ---
    def reenviar_produto(self, *, order_id, valor, motivo, aprovacao_id=None):
        return self._call("reenviar_produto", order_id=order_id, valor=valor, motivo=motivo,
                          aprovacao_id=aprovacao_id)

    def reimprimir_personalizacao(self, *, order_id, valor, personalizacao_correta=None,
                                  aprovacao_id=None):
        return self._call("reimprimir_personalizacao", order_id=order_id, valor=valor,
                          personalizacao_correta=personalizacao_correta,
                          aprovacao_id=aprovacao_id)

    def trocar_produto(self, *, order_id, sku_novo=None, valor, aprovacao_id=None):
        return self._call("trocar_produto", order_id=order_id, sku_novo=sku_novo, valor=valor,
                          aprovacao_id=aprovacao_id)

    def reembolsar(self, *, order_id, valor, motivo, aprovacao_id=None):
        return self._call("reembolsar", order_id=order_id, valor=valor, motivo=motivo,
                          aprovacao_id=aprovacao_id)

    # --- escalada, suspeita e supervisão ---
    def solicitar_aprovacao(self, *, acao, order_id=None, valor, justificativa):
        return self._call("solicitar_aprovacao", acao=acao, order_id=order_id, valor=valor,
                          justificativa=justificativa)

    def sinalizar_suspeita(self, *, conversation_id, sinais=None, evidencias):
        return self._call("sinalizar_suspeita", conversation_id=conversation_id, sinais=sinais,
                          evidencias=evidencias)

    def acionar_pessoa(self, *, area, assunto, contexto, urgencia=None):
        return self._call("acionar_pessoa", area=area, assunto=assunto, contexto=contexto,
                          urgencia=urgencia)

    def aprovar_acao(self, *, aprovacao_id, comentario=None):
        call = self._call("aprovar_acao", aprovacao_id=aprovacao_id, comentario=comentario)
        self.aprovadas.add(aprovacao_id)
        return call

    def registrar_cosmetovigilancia(self, *, conversation_id, sku, lote=None, descricao,
                                    fotos=None):
        return self._call("registrar_cosmetovigilancia", conversation_id=conversation_id,
                          sku=sku, lote=lote, descricao=descricao, fotos=fotos)
