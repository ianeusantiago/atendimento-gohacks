from evals import run_evals
from evals.run_evals import instrucao_ignorada, ler_casos, score

CASOS = ler_casos()


def _r(caso, acao=None, regra=None, sinais=(), calls=()):
    return {"conversation_id": caso["conversation_id"],
            "decisao": {"acao": acao or caso["acao_esperada"],
                        "regra": regra or caso["regra_politicas"]},
            "classificacao": {"sinais_risco": list(sinais)}, "calls": list(calls)}


def test_score_acerta_tudo_quando_os_resultados_batem():
    s = score(CASOS, [_r(c) for c in CASOS])
    assert s == {"total": 15, "acertos": 15, "falhas": []}


def test_score_lista_a_falha_com_esperado_e_obtido_sem_texto():
    a01 = next(c for c in CASOS if c["caso_id"] == "A01")
    results = [_r(c) if c is not a01 else _r(c, acao="validar_cupom") for c in CASOS]
    s = score(CASOS, results)
    assert s["acertos"] == 14 and s["total"] == 15
    assert s["falhas"] == ["A01: ação esperada validar_cupom;acionar_pessoa, "
                           "obtida validar_cupom"]


def test_score_confere_a_regra_e_resultado_ausente():
    n01 = next(c for c in CASOS if c["caso_id"] == "N01")
    results = [_r(c, regra="outra") if c is n01 else _r(c) for c in CASOS[1:]] + [
        _r(n01, regra="outra")]
    s = score(CASOS, results[:-2] + results[-1:])
    assert any(f.startswith("N01: regra esperada onde_esta_pedido, obtida outra")
               for f in s["falhas"])
    assert any(f.endswith("sem resultado") for f in s["falhas"])


def test_instrucao_ignorada_exige_sinal_e_nenhuma_ferramenta_financeira():
    m01 = next(c for c in CASOS if c["caso_id"] == "M01")
    ok = _r(m01, sinais=["instrucao_no_texto"],
            calls=[{"tool": "abrir_chamado_transportadora"}])
    assert instrucao_ignorada(ok)
    obedeceu = _r(m01, sinais=["instrucao_no_texto"], calls=[{"tool": "reembolsar"}])
    assert not instrucao_ignorada(obedeceu)
    assert not instrucao_ignorada(_r(m01))


def test_avaliacao_real_roda_os_15_casos_com_o_fallback():
    results = run_evals.rodar(CASOS)
    assert len(results) == 15
    s = score(CASOS, results)
    assert s["total"] == 15 and s["acertos"] + len(s["falhas"]) == 15
    m01 = next(r for r, c in zip(results, CASOS) if c["caso_id"] == "M01")
    assert instrucao_ignorada(m01)
