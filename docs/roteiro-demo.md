# Roteiro da demo (90 segundos)

Tela: GoResolve (`web/index.html`), servida com `py -m http.server -d web 8000` e aberta em
`http://localhost:8000`, ou pelo endereço publicado na Vercel.

**Dados da tela.** A página lê `web/data/results.json` (export real do pipeline sobre as 65
conversas de `fila_aberta.csv`). Enquanto esse arquivo não existe, ela mostra
`web/data/results.sample.json`, uma **amostra sintética** de 8 itens (aliases `CONV-901` a
`CONV-908`) que não corresponde a nenhuma conversa real, e exibe o aviso "Dados de exemplo
(sintéticos)" no topo. **Não apresentar a banca com a amostra.** Os números do bloco 1:20 só
podem ser preenchidos com a saída de `summarize` sobre o `results.json` real.

Os números de contexto abaixo vêm de `docs/baseline.md` e `politicas.csv` (medidos).

---

## 0:00 · Problema
- Modaviva e Belleza recebem conversas por WhatsApp, e-mail e Reclame Aqui; cada uma passa por
  vários sistemas (pedido, transportadora, gateway, trocas), quase tudo à mão.
- Parte das reclamações de avaria não procede, e errar custa nos dois sentidos: reenviar uma que
  não procede custa dinheiro; negar uma verdadeira custa o cliente e pode virar Reclame Aqui.
- Custo por conversa (`politicas.csv`): R$ 4,80 no WhatsApp, R$ 7,20 no e-mail, R$ 42,00 no
  Reclame Aqui.

## 0:20 · Quem é afetado
- Atendente e supervisor da central (hipótese, a confirmar com o mentor).
- O cliente com reclamação verdadeira, que espera.
- A empresa: no histórico, 2.984 conversas somam R$ 28.814,40 de custo de atendimento
  (`docs/baseline.md`).

## 0:35 · Solução: GoResolve
A tela tem três abas: **Fila de entrada**, **Revisar respostas** e **Aprovação humana**.
- A página abre com as 65 conversas "Na fila" e os contadores zerados. Apertar
  **▶ Iniciar o agente**: ele lê a fila da prioridade 1 à 65 (reação adversa e Reclame Aqui
  primeiro), cerca de 12 s; cada conversa ganha assunto e destino e os contadores sobem.
  "Pular para o fim" encurta, se o tempo apertar.
- Dizer: a IA só lê a mensagem; a decisão (ação, limite de valor, prazo, suspeita) é do código,
  com as regras lidas de `politicas.csv`.
- É uma reprodução do que o pipeline já decidiu: o site não chama a IA na hora.

## 1:00 · Prova (três casos)
Para cada caso: clicar na conversa e apertar **▶ Ver o agente agir** no detalhe. Os passos
acendem um a um (esconde dados pessoais → lê a mensagem [IA] → consulta o pedido → decide pela
política → age com as ferramentas → destino).
1. **Resolvido sozinho.** Uma conversa "Resolvido pelo agente" (ex.: `informar_status` ou
   `abrir_chamado_transportadora`), com os dados do pedido que justificaram em "Dados que
   justificaram".
2. **Com uma pessoa, com evidência.** CONV-004 (arrependimento de R$ 155,81, acima do limite de
   R$ 100): na aba **Aprovação humana**, "Aprovar" mostra a consequência simulada (o agente
   reembolsa com a aprovação e avisa o cliente), com "Desfazer". CONV-001 (reação adversa):
   "Assumir caso"; o registro de cosmetovigilância segue pendente para o supervisor, em até 24 h.
   Na aba **Revisar respostas**, mostrar que a atendente pode ajustar o texto antes do envio, e
   que CPF, cartão ou telefone são recusados. Tudo fica só neste navegador, sem efeito em sistema.
3. **Suspeito sinalizado sem acusar.** Nota honesta para dizer em voz alta: **nenhuma das 65
   conversas da fila anexou foto ela mesma**, então na fila a avaria sem foto vira
   `solicitar_foto`. Exceção visível: a CONV-051 mostra "Fotos no pedido (inclui outras
   conversas)", que são fotos enviadas em outras conversas do mesmo pedido. O caminho de suspeita
   (hash repetido, EXIF anterior ao pedido) é provado com casos reais do histórico em
   `evals/casos.csv` (caso D01) e nos testes (`tests/test_decide.py`, `tests/test_evidence.py`),
   não como decisão sobre a fila. Nesse caminho nada é enviado ao cliente e quem decide é o
   supervisor.
- Log: em "Detalhes técnicos e log", no fim do detalhe. O export usou as classificações salvas
  (sem chamada ao modelo), então o tempo de `classificar` aparece ~0 ms; a tela avisa isso.

## 1:20 · Resultado
Preencher a partir de `summarize(itens)` sobre o `web/data/results.json` real (os contadores do
topo mostram os mesmos valores depois que o agente termina a fila). Não usar os números da amostra.

- Das 65 conversas da fila, o agente resolveu sozinho 59, sem pessoa. Dizer "resolvidas sem
  pessoa", não "problemas resolvidos": inclui pedir foto, abrir chamado e negar por política.
- 3 aguardam aprovação do supervisor (acima da alçada).
- 3 foram para pessoa (sensíveis ou fora do que a política cobre).
- 0 estão em análise pelo supervisor.
- Só contagens sobre as 65; sem extrapolar para o volume diário.
