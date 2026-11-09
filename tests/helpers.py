"""Atalhos de teste sobre pipeline/case_builder.py (implementação única, a mesma do pipeline).

Mantém as assinaturas antigas (Dataset em vez de Gateway) para os testes existentes.
"""
from datetime import datetime

from pipeline.case_builder import build_case, conversa_e_agora as _conversa_e_agora
from pipeline.data import Dataset
from pipeline.decide import Case
from pipeline.gateway import CsvGateway
from pipeline.models import Classificacao
from pipeline.policy import load_policy


def conversa_e_agora(ds: Dataset, conversation_id: str) -> tuple[dict, datetime]:
    conv, now, _ = _conversa_e_agora(CsvGateway(ds), conversation_id)
    return conv, now


def case_da_conversa(ds: Dataset, conversation_id: str, cl: Classificacao) -> Case:
    gw = CsvGateway(ds)
    conv, now, _ = _conversa_e_agora(gw, conversation_id)
    return build_case(gw, conversation_id, now, cl, conv["order_id"], load_policy())
