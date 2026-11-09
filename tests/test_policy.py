from datetime import date

from pipeline.data import load_dataset
from pipeline.policy import load_policy


def test_policy_lida_de_politicas_csv():
    p = load_policy()
    assert p.limite_reenvio == 200.0
    assert p.limite_reembolso == 100.0
    assert p.limite_troca == 200.0
    assert p.prazo_dias == 7
    assert p.preparo["modaviva_personalizado"] == 3
    assert p.sla[("TransLeste", "SE")] == 2
    assert p.sla[("Rápido Sul", "N")] == 8
    assert p.sla[("Correio Ágil", "NE")] == 6
    assert len(p.sla) == 25
    assert p.regiao_por_uf["BA"] == "NE"
    assert len(p.regiao_por_uf) == 27
    assert date(2026, 11, 2) in p.feriados
    assert len(p.feriados) == 7
    assert "avaria_vazamento" in p.categorias
    assert p.categorias["avaria_vazamento"]["exige_foto"] is True
    assert p.categorias["avaria_vazamento"]["acoes_permitidas"] == [
        "solicitar_foto", "reenviar_produto"]
    assert p.categorias["troca_fragrancia"]["prazo_dias_corridos_do_recebimento"] == 30
    assert "Outros" in p.tags and len(p.tags) == 13


def test_dataset_loads():
    ds = load_dataset()
    assert len(ds.fila) == 65
    orfaos = sorted(r["order_id"] for r in ds.fila
                    if r["order_id"] and r["order_id"] not in ds.pedidos)
    # Pedidos da fila ausentes de pedidos.csv (lista vazia = nenhum orfao).
    assert orfaos == []
    for conv in ds.fila:
        msgs = ds.mensagens.get(conv["conversation_id"], [])
        assert [m["timestamp"] for m in msgs] == sorted(m["timestamp"] for m in msgs)
    assert sum(len(v) for v in ds.anexos.values()) == len(ds.todos_anexos)
    assert ds.historico and all(k == v["conversation_id"] for k, v in ds.historico.items())
    assert all(k == v["customer_id"] for k, v in ds.clientes.items())
