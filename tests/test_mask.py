"""Mascaramento de PII antes do modelo. Exemplos sinteticos, nunca linhas reais dos dados."""
from pipeline.mask import Pseudonymizer, contains_pii, mask_text


def test_cpf_some():
    out = mask_text("CPF 123.456.789-09")
    assert "123.456.789-09" not in out
    assert "[CPF]" in out
    assert "[CPF]" in mask_text("meu cpf e 12345678909 ok")


def test_cartao_some():
    out = mask_text("cartao 4111 1111 1111 1111 recusado")
    assert "4111" not in out
    assert "[CARTAO]" in out
    assert "[CARTAO]" in mask_text("4111111111111111")


def test_telefone_some():
    out = mask_text("liga no (11) 91234-5678 por favor")
    assert "91234-5678" not in out
    assert "[TEL]" in out
    assert "[TEL]" in mask_text("whats +55 11 912345678")


def test_telefone_sem_ddd_some():
    assert "91234-5678" not in mask_text("tel 91234-5678")
    assert "[TEL]" in mask_text("tel 91234-5678")
    assert "[TEL]" in mask_text("fixo 3456-7890")
    assert "[TEL]" in mask_text("cel 912345678")


def test_cpf_com_espaco_ou_ponto_some():
    assert "[CPF]" in mask_text("cpf 123 456 789 09")
    assert "123 456 789 09" not in mask_text("cpf 123 456 789 09")
    assert "[CPF]" in mask_text("cpf 123.456.789.09")


def test_nao_mascara_datas_ids_e_valores():
    for texto in ("em 2026-11-02 08:00 abri", "conversa CV000033", "pedido PED000047",
                  "paguei R$ 129,00", "R$ 1.299,90", "CEP 81017-103", "NF 000100231",
                  "02/11/2026 08:00", "rastreio CA927334850BR"):
        assert mask_text(texto) == texto, texto


def test_texto_sem_pii_intacto():
    texto = "Pedido PED123 nao chegou, valor R$ 89,90 em 02/11/2026"
    assert mask_text(texto) == texto
    assert not contains_pii(texto)


def test_contains_pii():
    assert contains_pii("CPF 123.456.789-09")
    assert not contains_pii(mask_text("CPF 123.456.789-09 tel (11) 91234-5678"))


def test_alias_estavel_e_distinto():
    p = Pseudonymizer()
    a = p.alias("CH000123")
    assert a == p.alias("CH000123")
    assert a == "C-001"
    assert p.alias("CH000999") == "C-002"


import pytest


@pytest.mark.parametrize("texto", ["123456789-09", "123.456.789/09", "123-456-789-09",
                                   "4111.1111.1111.1111", "3782 822463 10005"])
def test_formatos_extras_de_cpf_e_cartao_somem(texto):
    assert contains_pii(texto) and texto not in mask_text(f"dado {texto} fim")


def test_par_de_anos_nao_vira_telefone():
    assert mask_text("pedido de 2026 2027") == "pedido de 2026 2027"
    assert "[TEL]" in mask_text("ligue 3333-4444")
