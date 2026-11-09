"""Mascaramento de PII antes de qualquer texto ir ao modelo ou ao log.

Ordem: cartao (13-19 digitos), CPF, telefone. Um numero de 11 digitos sem separador
e ambiguo (CPF ou celular) e vira [CPF]: o que importa e nao sair em claro.
"""
import re

# Cartao: 13-19 digitos seguidos ou em grupos de 4 com o mesmo separador.
_CARTAO = re.compile(
    r"(?<![\w+])(?:\d{13,19}|\d{4}([ .-])\d{4}\1\d{4}\1\d{1,7}"
    r"|\d{4}[ .-]\d{6}[ .-]\d{5})(?![\w])")  # 4-6-5: Amex
# CPF: 3.3.3-2 com separador ponto, espaco ou hifen (o ultimo pode ser -, ., / ou espaco),
# 9 digitos + -2, ou 11 seguidos.
_CPF = re.compile(
    r"(?<![\w])(?:\d{3}[.\s-]\d{3}[.\s-]\d{3}[-./\s]\d{2}|\d{9}-\d{2}|\d{11})(?![\w])")
# Telefone BR com DDD: +55 opcional, (11) ou 11, 9 opcional, 4+4 digitos.
# Sem DDD: celular 9xxxx-xxxx (separador opcional) ou xxxx-xxxx com separador obrigatorio,
# para nao mascarar numeros soltos de 8 digitos.
_TEL = re.compile(
    r"(?<![\w])(?:(?:\+?55[\s-]?)?\(?\d{2}\)?[\s-]?9?\d{4}[\s-]?\d{4}"
    r"|9\d{4}[\s-]?\d{4}|(?!(?:19|20)\d\d[\s-](?:19|20)\d\d\b)\d{4}[\s-]\d{4})(?![\w])")
# (o lookahead deixa passar pares de anos como "2026 2027", que nao sao telefone)

_REGRAS = ((_CARTAO, "[CARTAO]"), (_CPF, "[CPF]"), (_TEL, "[TEL]"))


def mask_text(text: str) -> str:
    for padrao, marca in _REGRAS:
        text = padrao.sub(marca, text)
    return text


def contains_pii(text: str) -> bool:
    return any(padrao.search(text) for padrao, _ in _REGRAS)


class Pseudonymizer:
    """Troca um id (customer_id por padrao) por um apelido estavel (C-001, C-002...) na ordem
    em que aparece. prefixo muda o apelido (ex.: "CONV" -> CONV-001, usado no export)."""

    def __init__(self, prefixo: str = "C") -> None:
        self._mapa: dict[str, str] = {}
        self._prefixo = prefixo

    def alias(self, customer_id: str) -> str:
        if customer_id not in self._mapa:
            self._mapa[customer_id] = f"{self._prefixo}-{len(self._mapa) + 1:03d}"
        return self._mapa[customer_id]
