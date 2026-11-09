"""Sinais de reclamação suspeita a partir dos anexos (ver_anexos), em código, sem modelo.

Regra de politicas.csv (reclamacao_suspeita): só fatos verificáveis nos dados, nunca
impressão subjetiva. Quem decide é o supervisor; aqui só se juntam as evidências.
EXIF vazio é o normal no WhatsApp (o aplicativo remove os metadados) e nunca é sinal.
Os textos de `detail` descrevem o fato, sem acusar ninguém.
"""
import re
import unicodedata
from dataclasses import dataclass

# Nomes de software que indicam edição da imagem (comparação sem acento e sem caixa).
# Lista curta e explícita. No histórico há "Editor de Fotos do Galaxy" (6 anexos) e
# "Fotos do iOS" (4); o segundo é o app de galeria do iPhone e fica de fora (a confirmar).
SOFTWARE_EDICAO = ("editor", "photoshop", "lightroom", "snapseed", "picsart", "gimp",
                   "facetune")

# Descrições que começam por embalagem/caixa falam do pacote, não do produto: não dá para
# comparar com o produto do pedido, então não geram descricao_incoerente.
INICIO_EMBALAGEM = ("caixa", "embalagem", "itens")
# Palavras do nome do produto que não identificam o objeto.
PALAVRAS_IGNORADAS = {"personalizado", "personalizada", "iniciais", "nome", "foto", "brinde"}
# Mesmo objeto com outro nome (descrição visual -> nome do catálogo).
SINONIMOS = {"capinha": "case"}
CODIGO_PEDIDO = re.compile(r"\bped\d{6}\b")

# Sinais que bastam sozinhos para sinalizar (fato verificável contra outros dados).
# exif_software_edicao e descricao_incoerente só corroboram: um recorte no editor da
# galeria ou uma descrição genérica ("frasco quebrado") podem vir de cliente honesto.
SINAIS_FORTES = {"hash_repetido", "exif_fora_da_janela"}


@dataclass
class Signal:
    kind: str  # hash_repetido | exif_fora_da_janela | exif_software_edicao | descricao_incoerente
    detail: str


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


def _palavras(texto: str) -> set[str]:
    return {SINONIMOS.get(w, w) for w in re.findall(r"[a-z0-9]+", _norm(texto))
            if len(w) >= 4 and w not in PALAVRAS_IGNORADAS}


def _hash_repetido(a: dict, todos_anexos: list[dict]) -> Signal | None:
    outros = sorted({o["conversation_id"] for o in todos_anexos
                     if o["hash_perceptual"] == a["hash_perceptual"]
                     and o["anexo_id"] != a["anexo_id"]
                     and (o["customer_id"] != a["customer_id"] or o["order_id"] != a["order_id"])})
    if not outros:
        return None
    return Signal("hash_repetido", f"{a['anexo_id']}: mesma imagem (hash_perceptual) aparece em "
                                   f"outro cliente ou pedido, conversas {', '.join(outros)}")


def _exif_fora_da_janela(a: dict, pedido: dict) -> Signal | None:
    captura = a["exif_data_captura"]
    if not captura or captura[:10] >= pedido["data_pedido"][:10]:
        return None
    return Signal("exif_fora_da_janela", f"{a['anexo_id']}: data de captura {captura[:10]} "
                                         f"anterior à data do pedido {pedido['data_pedido'][:10]}")


def _software_edicao(a: dict) -> Signal | None:
    software = a["exif_software"]
    if not software or not any(s in _norm(software) for s in SOFTWARE_EDICAO):
        return None
    return Signal("exif_software_edicao", f"{a['anexo_id']}: metadado de software "
                                          f"de edição ({software})")


def _descricao_incoerente(a: dict, pedido: dict) -> Signal | None:
    desc = _norm(a.get("descricao_visual") or "").strip()
    if not desc:
        return None
    codigos = [c for c in CODIGO_PEDIDO.findall(desc) if c != _norm(pedido["order_id"])]
    if codigos:
        return Signal("descricao_incoerente", f"{a['anexo_id']}: etiqueta com número de outro "
                                              f"pedido ({codigos[0].upper()})")
    if desc.split()[0] in INICIO_EMBALAGEM:
        return None
    if _palavras(desc) & _palavras(pedido["descricao_produto"]):
        return None
    return Signal("descricao_incoerente", f"{a['anexo_id']}: descrição da imagem não cita o "
                                          f"produto do pedido ({pedido['descricao_produto']})")


def suspicion_signals(anexos: list[dict], pedido: dict, todos_anexos: list[dict]) -> list[Signal]:
    """Sinais verificáveis nos anexos da conversa. Vazio quando não há anexos."""
    sinais = []
    for a in anexos:
        for s in (_hash_repetido(a, todos_anexos), _exif_fora_da_janela(a, pedido),
                  _software_edicao(a), _descricao_incoerente(a, pedido)):
            if s:
                sinais.append(s)
    return sinais
