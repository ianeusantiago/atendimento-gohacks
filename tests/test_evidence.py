from functools import lru_cache

from pipeline.data import load_dataset
from pipeline.evidence import SINAIS_FORTES, suspicion_signals


@lru_cache(maxsize=1)
def _ds():
    return load_dataset()


def _anexo(**campos):
    """Anexo sintetico com o formato de anexos_conversas.csv."""
    base = {"anexo_id": "IMGT00001", "conversation_id": "ATT00001", "order_id": "GBHT00001",
            "customer_id": "CHT00001", "canal": "whatsapp", "tipo": "foto_produto",
            "hash_perceptual": "0000000000000001", "exif_data_captura": "",
            "exif_modelo_camera": "", "exif_software": "",
            "descricao_visual": "Body Mist Baunilha 200ml com o pote rachado."}
    base.update(campos)
    return base


PEDIDO = {"order_id": "GBHT00001", "customer_id": "CHT00001", "data_pedido": "2026-10-20",
          "descricao_produto": "Body Mist Baunilha 200ml"}


def _kinds(sinais):
    return {s.kind for s in sinais}


def test_sem_anexos_nenhum_sinal():
    assert suspicion_signals([], PEDIDO, [_anexo()]) == []


def test_exif_vazio_whatsapp_nunca_gera_sinal_sozinho():
    a = _anexo()
    assert suspicion_signals([a], PEDIDO, [a]) == []


def test_hash_repetido_em_outro_cliente():
    a = _anexo()
    outro = _anexo(anexo_id="IMGT00002", conversation_id="ATT00002", order_id="GBHT00002",
                   customer_id="CHT00002")
    assert _kinds(suspicion_signals([a], PEDIDO, [a, outro])) == {"hash_repetido"}


def test_hash_repetido_no_mesmo_pedido_nao_e_sinal():
    # mesmo cliente reenviando a mesma foto do mesmo pedido em outra conversa
    a = _anexo()
    outra_conversa = _anexo(anexo_id="IMGT00002", conversation_id="ATT00002")
    assert suspicion_signals([a], PEDIDO, [a, outra_conversa]) == []


def test_exif_anterior_ao_pedido():
    a = _anexo(exif_data_captura="2026-10-01 10:00:00", exif_modelo_camera="iPhone 15")
    assert _kinds(suspicion_signals([a], PEDIDO, [a])) == {"exif_fora_da_janela"}


def test_exif_depois_do_pedido_nao_e_sinal():
    a = _anexo(exif_data_captura="2026-10-25 10:00:00", exif_modelo_camera="iPhone 15")
    assert suspicion_signals([a], PEDIDO, [a]) == []


def test_software_de_edicao():
    a = _anexo(exif_data_captura="2026-10-25 10:00:00", exif_software="Editor de Fotos do Galaxy")
    assert _kinds(suspicion_signals([a], PEDIDO, [a])) == {"exif_software_edicao"}


def test_descricao_de_outro_produto():
    a = _anexo(descricao_visual="Necessaire estampada rasgado na costura.")
    assert _kinds(suspicion_signals([a], PEDIDO, [a])) == {"descricao_incoerente"}


def test_descricao_generica_de_embalagem_nao_e_sinal():
    a = _anexo(tipo="foto_embalagem", descricao_visual="Caixa da transportadora com a fita violada.")
    assert suspicion_signals([a], PEDIDO, [a]) == []


def test_etiqueta_com_numero_de_outro_pedido():
    a = _anexo(descricao_visual="Caixa da transportadora molhada; etiqueta com o número do "
                                "pedido PED000039 legível.")
    assert _kinds(suspicion_signals([a], PEDIDO, [a])) == {"descricao_incoerente"}


def test_detalhe_nunca_acusa():
    a = _anexo(exif_data_captura="2026-10-01 10:00:00", exif_software="Editor de Fotos do Galaxy",
               descricao_visual="Necessaire estampada rasgado na costura.")
    outro = _anexo(anexo_id="IMGT00002", order_id="GBHT00002", customer_id="CHT00002")
    for s in suspicion_signals([a], PEDIDO, [a, outro]):
        assert "fraude" not in s.detail.lower() and "golpe" not in s.detail.lower()


# --- dados reais do histórico ---

def test_d01_real_at104936_tem_hash_repetido_e_exif_fora_da_janela():
    ds = _ds()
    anexos = ds.anexos["CV000001"]
    pedido = ds.pedidos[anexos[0]["order_id"]]
    kinds = _kinds(suspicion_signals(anexos, pedido, ds.todos_anexos))
    assert "hash_repetido" in kinds
    assert "exif_fora_da_janela" in kinds


def _anexos_com_sinal(kind):
    """IDs dos anexos reais que, avaliados um a um, geram o sinal."""
    ds = _ds()
    return {a["anexo_id"] for a in ds.todos_anexos
            if kind in _kinds(suspicion_signals([a], ds.pedidos[a["order_id"]], ds.todos_anexos))}


def test_real_detecta_os_8_hashes_repetidos_entre_pedidos():
    ds = _ds()
    sinalizados = _anexos_com_sinal("hash_repetido")
    hashes = {a["hash_perceptual"] for a in ds.todos_anexos if a["anexo_id"] in sinalizados}
    assert len(hashes) == 8
    assert len(sinalizados) == 17


def test_real_detecta_os_10_exif_anteriores_ao_pedido():
    assert len(_anexos_com_sinal("exif_fora_da_janela")) == 10


def test_real_exif_vazio_nunca_gera_sinal_de_exif():
    ds = _ds()
    vazios = [a for a in ds.todos_anexos if not a["exif_data_captura"] and not a["exif_software"]]
    assert vazios
    for a in vazios:
        kinds = _kinds(suspicion_signals([a], ds.pedidos[a["order_id"]], ds.todos_anexos))
        assert not kinds & {"exif_fora_da_janela", "exif_software_edicao"}


def test_real_software_de_edicao_e_descricao_incoerente():
    # medido no histórico: 6 anexos com "Editor de Fotos do Galaxy"; 6 descrições de outro produto
    assert len(_anexos_com_sinal("exif_software_edicao")) == 6
    assert _anexos_com_sinal("descricao_incoerente") == {
        "IMG000010", "IMG000021", "IMG000074", "IMG000098", "IMG000102", "IMG000236"}


def test_descricao_vazia_ou_so_espacos_nao_quebra_nem_gera_sinal():
    for desc in ("", "   ", "\n\t"):
        a = _anexo(descricao_visual=desc)
        assert suspicion_signals([a], PEDIDO, [a]) == []


def test_sinais_fortes_sao_hash_e_exif_fora_da_janela():
    assert SINAIS_FORTES == {"hash_repetido", "exif_fora_da_janela"}


def test_real_sinais_fracos_sozinhos():
    # R6b medido: anexos cujo único tipo de sinal é fraco (não suspendem sozinhos)
    ds = _ds()
    sozinhos = {"exif_software_edicao": 0, "descricao_incoerente": 0}
    for a in ds.todos_anexos:
        kinds = _kinds(suspicion_signals([a], ds.pedidos[a["order_id"]], ds.todos_anexos))
        if kinds and not kinds & SINAIS_FORTES:
            for k in kinds:
                sozinhos[k] += 1
    assert sozinhos == {"exif_software_edicao": 6, "descricao_incoerente": 0}
    assert len(_anexos_com_sinal("hash_repetido") | _anexos_com_sinal("exif_fora_da_janela")) == 17
