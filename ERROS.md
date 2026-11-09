# ERROS: o que a IA errou, como percebi, o que mudou

## 2026-11-07 · A01: o classificador não marcou a dúvida de elegibilidade do cupom (evals 14/15)
- **O que aconteceu.** Na rodada real do proxy com o prompt v2 (`gpt-6-astra`, 65 chamadas),
  a conversa do caso A01 (fila, `cupom_promocao`) saiu sem o sinal `duvida_elegibilidade_cupom`
  (confiança 0,99). Sem o sinal, `decide.py` segue a política da categoria e a ação fica
  `validar_cupom`; o esperado em `evals/casos.csv` é `validar_cupom;acionar_pessoa`. A02 recebeu
  `sem_politica_aplicavel` e passou.
- **Como percebi.** `py -m evals.run_evals` imprimiu `acertos: 14/15` e
  `falha A01: ação esperada validar_cupom;acionar_pessoa, obtida validar_cupom`.
- **O que foi corrigido ou por que ficou.** Ficou como está, de propósito. A regra no código
  está certa e testada (`tests/test_decide.py`: com o sinal, A01 dá `validar_cupom;acionar_pessoa`).
  O prompt foi escrito de forma conservadora ("só marque quando claramente aplicável; nunca numa
  dúvida comum de cupom com código"), porque marcar demais mandaria para pessoa cupons que os
  dados resolvem. Forçar o caso mudando o prompt até passar, ou editando `casos.csv`, seria
  ajustar ao teste. A rodada não foi repetida (limite de duas rodadas da fila inteira).
- **Mudança de processo.** Ambiguidade virou sinal de risco modelado (o modelo é confiante demais:
  A01/A02 saíram com confiança 0,96 a 0,99, então `CONFIANCA_MINIMA` não separa o ambíguo). Para a
  próxima rodada: medir o prompt contra os dois ambíguos antes de rodar a fila inteira, e
  considerar extrair o código do cupom (`codigo_cupom`) para o código decidir a elegibilidade
  pelos dados de `cupons.csv` em vez de depender do sinal do modelo.
