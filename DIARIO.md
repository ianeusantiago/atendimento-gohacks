# DIARIO: quando e como cada parte foi feita, e por quê

Fonte: `git log`, `git show --stat`, `docs/verificacao.md` e `docs/superpowers/handoff-2026-11-07.md`. O que não está nessas fontes aparece como NÃO VERIFICADO ou "a confirmar".

## Estado em 07/11/2026 15:20 (HEAD 2dcef47, branch feat/agente-triagem = main)
Medido agora, nesta sessão de documentação:
- `.venv/Scripts/python.exe -m pytest -q`: 476 passed.
- `node --test web/render.test.js`: 27 testes, 27 passaram, 0 falharam.
- `.venv/Scripts/python.exe -m evals.run_evals`: acertos 14/15; falha A01 (esperada `validar_cupom;acionar_pessoa`, obtida `validar_cupom`).
- Deploy: https://goresolve.vercel.app (projeto Vercel `goresolve`, publicado de dentro de `web/` com `vercel deploy --prod`). Conferido com `curl` que o `render.js` publicado tem `tempoPoupado` e que `data/results.json` publicado tem `tempo_referencia`. Os cliques no site publicado: NÃO VERIFICADO.
- Modelo do proxy: `gpt-6-astra` (padrão em `pipeline/config.py`; o `.env` pode trocar por `AI_PROXY_MODEL`, NÃO VERIFICADO se troca).

## 2026-11-07 15:11 · 2dcef47 · Marcar como resolvido e tempo poupado estimado
- **O quê:** botão "✓ Marcar como resolvido" (e "Reabrir") no detalhe de casos humanos; "✓ resolvido" na fila; na aba Impacto, "resolvidos pela atendente" e "≈ 12 h 00 min de trabalho poupado"; coluna `resolvido` no CSV.
- **Como:** `pipeline/export.py` ganhou `tempo_referencia()`, que lê `tempo_por_conversa.csv` e grava no export a média de `minutos_trabalhados` (12,2 min em 2.654 conversas). O schema público aceita o campo opcional `tempo_referencia`. A tela calcula `tempoPoupado` = conversas automáticas (59) × média. Resolvidos ficam no `localStorage` (`atendimento-gohacks:resolvidos:v1`).
- **Por quê:** pedido do Ian depois de conversa com mentor ("um atendente tem um escopo maior de coisas a resolver"); escolheu estas duas funções da lista proposta.
- **Prova:** testes "tempo poupado = automáticas × média histórica" e "marcar como resolvido só em caso humano..." em `web/render.test.js`; export regerado só mudou tempos do log (`ms`) e ganhou `tempo_referencia`.
- **Não testado:** a premissa de que uma conversa automática pouparia a média histórica inteira: estimativa, não medição.

## 2026-11-07 15:05 · d3f3f4d · Aba Impacto, encaminhar com nota, respostas prontas e CSV
- **O quê:** aba "Impacto" (% resolvido pelo agente, casos para pessoa, prazo apertado, barras por assunto e canal); "Encaminhar para outra área" com nota interna no detalhe; "Respostas prontas" na revisão; botão "Baixar CSV da fila".
- **Como:** funções puras em `web/render.js` (`renderImpacto`, `calcularImpacto`, `renderEncaminhar`, `RESPOSTAS_PRONTAS`, `paraCsv`). Áreas iguais às de `pipeline/tools.py` (`AREAS`). CSV com `;`, BOM e prefixo `'` em célula que começa com `= + - @` (evita fórmula). Nota interna recusada com CPF, cartão ou telefone (`temPii`).
- **Por quê:** mesmo pedido do mentor; funções escolhidas pelo Ian para explicar até 16:30.
- **Prova:** 3 testes novos em `web/render.test.js` (CSV protege fórmula; impacto conta; respostas prontas sem "reembolso", "estorno", "dias", "R$", "garant").
- **Não testado:** abrir o CSV no Excel de verdade (só conferido o texto gerado: 66 linhas).

## 2026-11-07 14:54 · 0eeeb0a · Aprovação com motivo e lote; fila com filtros, prazo e teclado
- **O quê:** rejeitar exige motivo; aprovação em lote; o cartão mostra a resposta que vai ao cliente; fila com filtros (destino, canal, busca), prazo de primeira resposta e navegação por setas.
- **Como:** `renderApprovals(..., opts)`, `prazoResposta`, `passaFiltro`, `renderFiltros` em `web/render.js`; estado e cliques em `web/app.js`; motivo em `atendimento-gohacks:motivos:v1`.
- **Por quê:** pedido do Ian ("faça a parte da aprovação humana e a fila").
- **Prova:** testes da tela (22 na época, segundo a sessão; hoje 27).
- **Não testado:** leitor de tela e teclado completos (acessibilidade): NÃO VERIFICADO.

## 2026-11-07 14:19 · 4b4c66c · Belleza sem acento
- **O quê:** a grafia da marca passou de "Belleza" para "Belleza" em 17 arquivos: site (`web/index.html`), export (`pipeline/export.py`), schema (`schemas/resultado_publico.schema.json`), testes, `web/data/results.json` e documentos (CLAUDE.md, SPEC.md, `docs/baseline.md`, `docs/roteiro-demo.md` e outros). Fonte: `git show --stat 4b4c66c`.
- **Como:** troca do texto nos arquivos. O corpo do commit só registra: "pytest 476; node 20/20; evals 14/15".
- **Por quê:** o título do commit diz "grafia correta da marca". Quem confirmou a grafia: a confirmar (pergunta ao Ian).
- **Prova:** os três comandos do "Estado" acima, rodados por mim em HEAD.
- **Não testado:** se sobrou a grafia antiga em algum arquivo fora desses 17: NÃO VERIFICADO.

## 2026-11-07 13:45 · 9612f8f · Deploy do web/ na Vercel
- **O quê:** dois arquivos novos em `web/`. `web/.vercelignore` tem `render.test.js` e `.gitkeep`: a Vercel não publica o teste nem o marcador vazio. `web/.gitignore` tem `.vercel` e `.env*`: o Git não guarda a pasta local da Vercel nem arquivos de segredo.
- **Como:** o site é estático (HTML, JS, CSS, fontes e JSON). Pela configuração, o que vai a público é a pasta `web/`: `index.html`, `app.js`, `render.js`, `styles.css`, `fonts/` e `data/` (com `results.json`, o export público com pseudônimos CONV-xxx). Não entra nada de `pipeline/`, `out/` nem dos dados originais. O conteúdo realmente publicado não foi conferido.
- **Por quê:** `docs/roteiro-demo.md` diz que a tela pode ser aberta "pelo endereço publicado na Vercel". O motivo além disso: a confirmar.
- **Prova:** `git show --stat 9612f8f` (2 arquivos, 4 linhas). URL: URL NÃO REGISTRADA no repositório (busca por "vercel.app" não achou nada).
- **Não testado:** o deploy em si e a conferência em janela anônima. `docs/verificacao.md` (seção NÃO VERIFICADO) diz que ainda não havia link.

## 2026-11-07 13:22 a 13:41 · a4f7588, ee301aa, 2794664, ff60b85, 4602dfd, 3fa1720, 08f0b13, b3b4065, f439a49 · Tela GoResolve
- **O quê** (arquivos `web/index.html`, `web/app.js`, `web/render.js`, `web/styles.css`, `web/render.test.js`, `docs/roteiro-demo.md`):
  - a4f7588 (13:22): duas abas, fila com o detalhe da conversa ao lado, resposta editável antes do envio, identidade do brandbook.
  - ee301aa (13:23): botão "Ver o agente agir": os passos do log acendem um a um (esconde dados, lê, consulta o pedido, decide, age). A etiqueta diz o que é IA (só "Lê a mensagem") e o que é código (o resto).
  - 2794664 (13:25): design minimalista. Fundo branco, azul de marca `#2659a5`, cinzas, vermelho só para alerta, fonte Poppins (arquivos em `web/fonts/`).
  - ff60b85 (13:30): passos já aparecem com visto; Aprovar, Rejeitar, Assumir e Marcar como visto mostram a consequência simulada, com "Desfazer".
  - 4602dfd (13:32): menos informação na primeira leitura; códigos técnicos ficam em "Detalhes técnicos e log".
  - 3fa1720 (13:34): a página abre com as 65 conversas "Na fila". "Iniciar o agente" lê uma por vez (`PASSO_MS = 180` em `app.js`), da prioridade 1 à 65; sobem contadores e barra. Há "Pular para o fim" e "Rodar de novo".
  - 08f0b13 (13:35): tira a frase e a data do topo.
  - b3b4065 (13:37): terceira aba, "Revisar respostas", com contador. Só para casos de aprovação e pessoa (`podeEditar` em `render.js`).
  - f439a49 (13:41): `docs/roteiro-demo.md` descreve as três abas e a animação.
- **Como:** `render.js` monta o HTML a partir do JSON; `app.js` liga os botões, guarda o estado e roda os temporizadores. `render.test.js` foi de 15 para 20 testes (os corpos dos commits registram 17, 18, 19, 20).
- **Por quê:** tornar a demo de 90 segundos clara para a banca. O pedido original de cada mudança não está no repositório: a confirmar.
- **O que é real e o que é simulação (lido no código):**
  - "O agente lê a fila ao vivo" e a linha do tempo são ANIMAÇÃO sobre resultados já prontos. `loadData` só faz `fetch` de `data/results.json`; não há chamada ao modelo nem ao proxy no navegador. O roteiro diz: "é uma reprodução do que o pipeline já decidiu".
  - Editar a resposta e aprovar não fazem nada além do navegador. Edições e decisões vão para o `localStorage` (chaves `atendimento-gohacks:edicoes:v1` e `atendimento-gohacks:decisoes:v1`). Nada vai a servidor nem ao cliente. A "consequência" é um texto (`consequencia` em `render.js`), e o código diz "é simulação: o site não executa nada".
  - Ao salvar uma edição, `temPii` recusa texto parecido com CPF, cartão ou telefone (anos como "2026 2027" passam). É checagem de padrão, não garantia.
  - Com "movimento reduzido" ligado no sistema, o resultado aparece direto, sem animação.
- **Prova:** `node --test web/`: 20/20. Testes novos, pelo nome: "edição só antes do envio...", "texto editado com CPF, cartão ou telefone é recusado...", "agente em ação: um passo por etapa do log...", "decisão humana mostra a consequência simulada...", "fila antes do agente: conversas 'Na fila'...".
- **Não testado:** a tela num navegador real, no celular e com leitor de tela: NÃO VERIFICADO (os testes Node só conferem o HTML gerado). Os "cerca de 12 s" do roteiro batem com 65 x 180 ms = 11,7 s (conta, não medição em tela).
- **Afirmações antigas que estes commits tornaram falsas:** nenhuma encontrada nos três arquivos (só o "15 da tela" de PERGUNTAS.md, atualizado para 20).

## O que de docs/verificacao.md está corrigido e o que segue aberto (conferido em 07/11 no git log)
- Corrigidos: 3a (prazo de 24 h, 8dea652); 3b (reação adversa sem pedido, 8dea652; classificador que escala, d3a61a0); 7 (instrução no texto, b1adc81 e d3a61a0); 2 (sinal fraco e motivo "Foto coerente", b1adc81); 5 (máscara, d3a61a0); 1 (`aprovacao_id`, d3a61a0).
- Ainda abertos: item 12 do roteiro (`docs/roteiro-demo.md` cita só a CONV-051 como exceção de foto; `docs/verificacao.md` diz que são 5 itens); item 12 de `docs/baseline.md` (trechos superados). A tabela de ações de `docs/baseline.md` ("Execução da fila") também está velha: diz `validar_cupom` 5, `acionar_pessoa` 1 e pendentes 11. A fila regerada hoje dá `validar_cupom` 4, `acionar_pessoa` 2 e pendentes 10. As outras 13 linhas batem. Não corrigi: não é arquivo meu.

## 2026-11-07 13:11 · d3a61a0 · Achados da revisão final da branch
- **O quê:** dez correções apontadas pela revisão final da branch inteira.
  - `pipeline/decide.py`: a trava de instrução no texto também barra `cancelar_pedido`, porque o cancelamento faz estorno integral (`COM_DINHEIRO`). Os sinais fracos agora entram na decisão (`_por_categoria`/`_reclamacao_fisica`), em vez de trocar o texto depois. `e_reacao_adversa` aceita a classificação ou o dict dela.
  - `pipeline/tools.py`: `acionar_pessoa` só aceita as áreas de `ferramentas.csv` (`AREAS`). O valor acima do limite só passa com um `aprovacao_id` aprovado por `aprovar_acao` (`ToolBox.aprovadas`).
  - `pipeline/executor.py`: a área padrão passou de "atendimento" para "supervisao". O registro de cosmetovigilância com prazo vencido diz "PRAZO VENCIDO".
  - `pipeline/llm.py`: um `x-ratelimit-reset` negativo, NaN ou infinito vira espera crescente (`2 ** tentativa`: 1 s e depois 2 s).
  - `pipeline/run.py`: quando o classificador escala e o texto tem termo de sintoma (`_SINTOMA`), a conversa segue o caminho de reação adversa e fica no grupo 0 da fila. A regra única vem de `decide.e_reacao_adversa`.
  - `pipeline/mask.py`: mascara CPF `ddddddddd-dd`, `ddd.ddd.ddd/dd`, `ddd-ddd-ddd-dd` e cartão com pontos ou 4-6-5. Pares de anos ("2026 2027") não viram telefone.
  - `pipeline/fatos.py`: o rótulo virou "Fotos no pedido (inclui outras conversas)".
- **Como:** um teste novo para cada ponto (`tests/test_decide.py`, `test_tools.py`, `test_llm.py`, `test_mask.py`, `test_run.py`). `test_tools.py` e `test_respostas.py` foram ajustados para a aprovação real e a área "supervisao".
- **Por quê:** a revisão final achou que (1) uma ordem no texto ainda cancelava com estorno sozinha; (2) a área "atendimento" não existe em `ferramentas.csv`; (3) um cabeçalho de 429 inválido derrubava a classificação; (4) quando o classificador escalava, a reação adversa perdia as ações obrigatórias; (5) o prazo vencido não tinha aviso; (6) o motivo era trocado por texto; (7) a regra de reação adversa estava duplicada; (8) qualquer `aprovacao_id` liberava valor; (9) a máscara tinha lacunas; (10) o rótulo das fotos enganava.
- **Prova:** pytest 476 passed; `node --test web/render.test.js` 15/15; `evals.run_evals` 14/15 (falha A01, já em ERROS.md). Fila regerada com `--use-fallback`: nenhuma decisão mudou, só o rótulo das fotos e os tempos.
- **Não testado:** a lista de termos de sintoma (`_SINTOMA`) não foi medida em dados reais; os termos são "a confirmar". O formato das áreas aceito pela API real do evento é NÃO VERIFICADO.

## 2026-11-07 13:06 · 8dea652 · Reação adversa: pedido divergente e prazo de 24 h
- **O quê:** `pipeline/decide.py` (`e_reacao_adversa`, `reacao_adversa_sem_pedido`), `pipeline/run.py` (`_decidir`, `relato_em`), `pipeline/executor.py` (`_reacao_adversa`).
- **Como:** quando a conversa cita um pedido de outro cliente ou diferente do vinculado, a reação adversa mantém `orientar_suspensao_uso` e o registro pendente. O prazo do registro conta da abertura da conversa (`data_abertura`), não do "agora" da fila.
- **Por quê:** itens 3b e 3a de `docs/verificacao.md`.
- **Prova:** dois testes novos em `tests/test_run.py`. D03 (CV000028): o prazo passou de 03/11 08:00 para 02/11 11:02 (relato em 01/11 11:02 + 24 h). pytest 459 passed; evals 14/15.
- **Não testado:** relato em mensagem posterior à abertura (o prazo continua contando da abertura).

## 2026-11-07 13:04 · b1adc81 · Instrução no texto e sinal fraco
- **O quê:** `pipeline/decide.py`. Com `instrucao_no_texto`, as ferramentas de dinheiro (reembolsar, reenviar, trocar, reimprimir) não rodam sozinhas: vão para `acionar_pessoa` com `ferramenta_sugerida`. Com sinal fraco na foto, o motivo não diz mais "Foto coerente com o pedido".
- **Por quê:** itens 7 e 2 de `docs/verificacao.md`. Antes, uma mensagem que era só uma ordem ("reembolse") virava reembolso automático dentro da alçada.
- **Prova:** quatro testes em `tests/test_decide.py`. M01 continua com `abrir_chamado_transportadora`. pytest 457 passed; evals 14/15.
- **Não testado:** chamada real ao proxy depois da mudança (rodou só com `--use-fallback`).

## Commits anteriores (outra máquina, 11:00 a 12:55)
Estes 28 commits foram feitos pela sessão anterior. O "o quê" vem do `git log`; o resumo do como e do por quê está em `docs/superpowers/handoff-2026-11-07.md` (seções "Decisões e regras" e "O que FALTA"). Hora e minuto por commit: `git log --date=format:"%H:%M"`.

| Hash | O quê | Prova registrada |
|---|---|---|
| 8fc90f5 | Design e plano do agente | docs/superpowers |
| 6f92372 | Perfil dos dados, baseline e SPEC.md | docs/baseline.md |
| cce10a3, 6f805f1, fb2b14e, bbb6b6b | 15 casos de avaliação e revisões do Ian (D03, D04, N06, A01, A02) | evals/casos.csv |
| f6f1f7d, 7eed35c | Interface Gateway e CsvGateway | pipeline/gateway.py, tests/test_gateway.py |
| 52fe351 | Dados e política lidos de politicas.csv | pipeline/data.py, policy.py |
| cd00ed1, c28d1e4 | Configuração, máscara de PII, cliente do modelo | pipeline/config.py, mask.py, llm.py |
| 3a67688 | Prazos em dias úteis | 6.092/6.092 pedidos batem com `data_prometida` (handoff) |
| 9b16b3a, cb6992b, e545f41 | Sinais de suspeita e decisão por precedência; prazo antes da foto | pipeline/evidence.py, decide.py |
| 1858bea, d47481f | Pedido e anexos na data da conversa (D04, N06, R6e) | pipeline/asof.py, context_rules.py |
| c3da8c4 | ToolBox com papéis e limites; respostas por template | pipeline/tools.py, respostas.py |
| 435d7e6, 8e759a2 | Execução da fila; rastreio parado; prazo vencido | pipeline/run.py, executor.py |
| 74ec6f8, b966dca | Ambiguidade de cupom, avaliação, export público | evals/run_evals.py, pipeline/export.py |
| fec6de4, cd5006c, 2809a72 | Tela estática no padrão Grupo Exemplo | web/ |
| a23ff6c, e5212d3 | Passagem de bastão | docs/superpowers/handoff-2026-11-07.md |
| 026887e | Verificação (12 itens) | docs/verificacao.md |

O que não foi testado em cada um desses commits: NÃO VERIFICADO individualmente. O consolidado está em `docs/verificacao.md`, seção do que não foi verificado.
