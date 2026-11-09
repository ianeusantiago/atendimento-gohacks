# ESTUDAR: o que preciso entender para explicar cada commit

Só o documentador atualiza este arquivo, quando o Ian disser "documente". Cada commit relevante cria ou atualiza um tema. Regra: nenhum tema pode ficar "só o agente sabe". Material de apoio em `estudo/`.

## Modelo de entrada
```markdown
## <tema> · commit <hash>
- Preciso explicar: a frase que a banca vai querer ouvir
- Onde está: arquivo e função
- Estudo (15 min): 1) abrir o arquivo  2) rodar o comando  3) mudar uma coisa e ver o que quebra
- Teste de compreensão: uma pergunta que respondo em 30 s, sem olhar
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s
```

## Temas para começar (valem para qualquer projeto; o documentador liga cada um ao arquivo real)
- [ ] **O caminho do dado.** Explicar as etapas na ordem, o que cada uma produz e o que não pode fazer. Onde: o arquivo do orquestrador. Estudo: siga um caso do começo ao fim e anote a saída de cada etapa. Teste: o que acontece se uma etapa falhar?
- [ ] **Por que a decisão é código.** Três motivos: repetibilidade (o modelo não garante repetir a resposta), injeção (o texto dos dados pode tentar dar ordens) e regra que muda (edita-se um arquivo). Teste: se uma regra mudar amanhã, o que você edita?
- [ ] **Segunda leitura independente.** Uma checagem em regras, que não confia no modelo e só empurra para o humano. Teste: por que existe se já há um modelo lendo?
- [ ] **Validação por schema e fallback.** Saída inválida vai para humano. Estudo: quebre o JSON de propósito e veja o resultado. Teste: o que acontece se o modelo responder lixo?
- [ ] **Verificador.** Confere dados, números e promessas antes de qualquer saída. Estudo: tente fazer passar uma promessa proibida. Teste: o que ele não consegue pegar?
- [ ] **Como ler as medições.** Gabarito conhecido x casos novos, baseline sem IA, vazamento (regras escritas olhando os dados de teste). Estudo: monte uma tabela com o que cada número prova e o que não prova. Teste: por que 100% não basta?
- [ ] **Injeção de prompt.** Texto do cliente ou dos dados tentando dar ordens ao sistema. Estudo: pesquise o item de prompt injection do OWASP para LLMs. Teste: por que o código não é convencido e o modelo poderia ser?
- [ ] **Dados pessoais.** LGPD é a lei brasileira; GDPR é a europeia; nos EUA há leis estaduais. Minimização e pseudonimização: o modelo recebe só o necessário. Teste: o que você mascara antes de ligar com dados reais?
- [ ] **Claude Code x Claude API.** Claude Code constrói o projeto; a API roda dentro do produto. Medir um não é medir o outro. Teste: o que ainda não foi provado sobre o modelo do produto?
- [ ] **Modelo local x Claude.** O que serve como medição barata e qual é o limite (modelo pequeno). Teste: o que uma medição local permite afirmar?
- [ ] **Métrica de processo x de negócio.** Processo: acertos contra o gabarito. Negócio: o resultado que o dono do desafio quer mudar. Teste: como você mediria a de negócio com dados reais?
- [ ] **Corrigir a IA e registrar.** Erro, como percebi, o que mudou. É o que mais pesa em Modelagem. Teste: conte um erro da IA em três passos, começando por como você percebeu.

## Temas do projeto (criados pelo documentador a cada commit)

### Onde cada tema inicial está neste projeto
| Tema inicial | Arquivo real |
|---|---|
| O caminho do dado | `pipeline/run.py` (`run_conversation`: mascarar → classificar → consultar_pedido → decidir → executar) |
| Por que a decisão é código | `pipeline/decide.py` (`decide`, precedência no docstring) |
| Segunda leitura independente | `pipeline/evidence.py` (sinais em código), `pipeline/llm.py` (`_INSTRUCAO`, regex além do modelo) |
| Validação por schema e fallback | `pipeline/llm.py` (`_parse` + `schemas/`), `fallback/classificacoes.json`, `--use-fallback` |
| Verificador | `docs/verificacao.md` (12 itens), `pipeline/export.py` (`conferir`) |
| Como ler as medições | `evals/run_evals.py`: 14/15; baseline em `docs/baseline.md` |
| Injeção de prompt | `pipeline/decide.py` (trava `INSTRUCAO`), caso M01 em `evals/casos.csv` |
| Dados pessoais | `pipeline/mask.py`, `pipeline/export.py` (pseudônimos CONV/PED/C) |
| Corrigir a IA e registrar | `ERROS.md` (A01) |

## Ordem no texto não move dinheiro · commits b1adc81, d3a61a0
- Preciso explicar: se a mensagem do cliente tenta dar uma ordem ao sistema ("reembolse", JSON forjado), nenhuma ferramenta que mexe com dinheiro roda sozinha. Ferramentas de informação seguem normais.
- Onde está: `pipeline/decide.py`, final de `decide` (`INSTRUCAO`, `COM_DINHEIRO`).
- Estudo (15 min): 1) leia o final de `decide`; 2) rode `.venv\Scripts\python -m pytest -q tests/test_decide.py -k instrucao`; 3) tire `cancelar_pedido` de `COM_DINHEIRO` e veja qual teste quebra.
- Teste de compreensão: por que o M01 continua abrindo chamado na transportadora mesmo com instrução escondida?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Sinal forte x sinal fraco na foto · commits b1adc81, d3a61a0
- Preciso explicar: só `hash_repetido` e `exif_fora_da_janela` bloqueiam. Edição e descrição genérica só acompanham como evidência, e aí o motivo não pode dizer "foto coerente".
- Onde está: `pipeline/evidence.py` (`SINAIS_FORTES`), `pipeline/decide.py` (`_reclamacao_fisica`, parâmetro `sinais`).
- Estudo: rode `pytest -q tests/test_decide.py -k sinal` e leia `test_sinal_fraco_nao_afirma_foto_coerente`.
- Teste de compreensão: por que o editor da galeria sozinho não é suspeita?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Reação adversa nunca se perde · commits 8dea652, d3a61a0
- Preciso explicar: a reação adversa sempre gera orientar a suspensão do uso mais um registro de cosmetovigilância pendente para o supervisor. Isso vale com pedido divergente, com pedido de outro cliente e quando o classificador desiste (por termos de sintoma no texto, "a confirmar"). O prazo de 24 h conta do relato; vencido, aparece "PRAZO VENCIDO".
- Onde está: `pipeline/decide.py` (`e_reacao_adversa`, `reacao_adversa_sem_pedido`), `pipeline/run.py` (`_decidir`, `_SINTOMA`, `relato_em`), `pipeline/executor.py` (`_reacao_adversa`).
- Estudo: rode `pytest -q tests/test_run.py -k reacao` e confira no `out/results.json` o prazo do CV000028 (02/11 11:02).
- Teste de compreensão: de onde conta o prazo e por que não do "agora" da fila?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Limite e aprovação no ToolBox · commit d3a61a0
- Preciso explicar: o ToolBox é a última barreira. Valor acima do limite só passa com um `aprovacao_id` que o supervisor aprovou de verdade (`aprovar_acao`), e `acionar_pessoa` só aceita as áreas de `ferramentas.csv`.
- Onde está: `pipeline/tools.py` (`ToolBox._call`, `aprovadas`, `AREAS`).
- Estudo: rode `pytest -q tests/test_tools.py` e leia `test_aprovacao_inventada_nao_libera_valor_acima_do_limite`.
- Teste de compreensão: por que a barreira fica no ToolBox e não só no `decide`?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Resiliência ao proxy (429) · commit d3a61a0
- Preciso explicar: com limite de requisições, o sistema espera e tenta de novo (até 3 vezes). Um cabeçalho inválido vira espera crescente e nunca um erro. Sem resposta, a conversa vai para pessoa.
- Onde está: `pipeline/llm.py` (`_espera_429`, `classify`).
- Estudo: rode `pytest -q tests/test_llm.py -k 429`.
- Teste de compreensão: o que acontece com a fila se o proxy cair no meio?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Máscara de PII · commit d3a61a0
- Preciso explicar: CPF, cartão e telefone são trocados por `[CPF]`, `[CARTAO]` e `[TEL]` antes de ir ao modelo e aos logs. A ordem importa: cartão, depois CPF, depois telefone.
- Onde está: `pipeline/mask.py`.
- Estudo: rode `pytest -q tests/test_mask.py` e teste `mask_text` com um CPF seu inventado.
- Teste de compreensão: por que "2026 2027" não pode virar `[TEL]`?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

### Cobertura (arquivos dos commits b1adc81, 8dea652, d3a61a0 → tema)
| Arquivo | Tema |
|---|---|
| pipeline/decide.py | Ordem no texto; Sinal forte x fraco; Reação adversa |
| pipeline/run.py | Reação adversa |
| pipeline/executor.py | Reação adversa; Limite e aprovação (área) |
| pipeline/tools.py | Limite e aprovação no ToolBox |
| pipeline/llm.py | Resiliência ao proxy |
| pipeline/mask.py | Máscara de PII |
| pipeline/fatos.py | Sinal forte x fraco (rótulo das fotos) |
| tests/*.py | o tema do arquivo testado |
| web/data/results.json | Dados pessoais (export público, só o rótulo mudou) |


## Tela GoResolve: o HTML e o desenho · commits a4f7588, 2794664, 4602dfd, 08f0b13 · arquivos `web/index.html`, `web/styles.css`, `web/fonts/`
- Preciso explicar: a tela é uma página estática com três abas (Fila de entrada, Revisar respostas, Aprovação humana). O desenho é minimalista: fundo branco, azul de marca `#2659a5`, vermelho só para alerta, fonte Poppins.
- Onde está: `web/index.html` (estrutura e abas), `web/styles.css` (variáveis `--azul`, `--vermelho` no `:root`).
- Estudo (15 min): 1) abra `web/index.html` e ache as três abas; 2) rode `py -m http.server -d web 8000` e abra `http://localhost:8000`; 3) mude `--azul` em `styles.css` e veja o que muda.
- Teste de compreensão: por que o vermelho aparece só em alerta?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Tela GoResolve: o agente "ao vivo" é animação · commits ee301aa, ff60b85, 3fa1720 · arquivos `web/app.js`, `web/render.js` (`renderAgente`, `PASSOS`)
- Preciso explicar: ao apertar "Iniciar o agente", a tela mostra, uma a uma (180 ms cada), conversas que o pipeline já decidiu. É animação sobre `data/results.json`. Não chama modelo nenhum. O que é real é o pipeline que gerou esse JSON.
- Onde está: `web/app.js` (`iniciar`, `PASSO_MS`, `tocar`, `loadData`); `web/render.js` (`PASSOS`, `renderAgente`).
- Estudo: 1) leia `iniciar` e `loadData`; 2) procure no código qualquer chamada ao proxy (não há); 3) rode `node --test web/` e leia o teste "agente em ação".
- Teste de compreensão: se a banca perguntar "isso roda a IA agora?", o que você responde em 20 s?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Tela GoResolve: edição e decisão humana (simuladas) · commits a4f7588, b3b4065, ff60b85 · arquivos `web/app.js`, `web/render.js` (`podeEditar`, `temPii`, `consequencia`)
- Preciso explicar: a atendente pode editar a resposta antes do envio (só casos de aprovação e pessoa). Salvar e aprovar gravam no `localStorage` do navegador. Nada é enviado. A consequência mostrada é só um texto.
- Onde está: `web/render.js` (`podeEditar`, `temPii`, `consequencia`); `web/app.js` (`writeStore`, cliques de salvar e decidir).
- Estudo: 1) edite uma resposta e recarregue a página; 2) escreva um número parecido com telefone e veja a recusa; 3) abra o `localStorage` nas ferramentas do navegador.
- Teste de compreensão: o que é real e o que é simulado quando o supervisor clica em "Aprovar"?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Testes da tela · commits a4f7588 a b3b4065 · arquivo `web/render.test.js`
- Preciso explicar: 20 testes Node conferem o HTML gerado por `render.js` (ordem da fila, edição, PII, passos, consequência). Não abrem navegador.
- Onde está: `web/render.test.js`.
- Estudo: rode `& "C:\Program Files\nodejs\node.exe" --test web/` (20 passam) e quebre uma regra em `podeEditar` para ver qual teste falha.
- Teste de compreensão: o que os testes Node não provam sobre a tela?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Deploy estático na Vercel · commit 9612f8f · arquivos `web/.vercelignore`, `web/.gitignore`
- Preciso explicar: só a pasta `web/` é publicada. `.vercelignore` deixa de fora `render.test.js` e `.gitkeep`. `.gitignore` impede de guardar `.vercel` e `.env*`. A URL não está registrada no repositório.
- Onde está: os dois arquivos acima.
- Estudo: leia os dois arquivos (2 linhas cada) e liste o que vai a público em `web/`.
- Teste de compreensão: o que um visitante consegue baixar desse site, e por que o token do proxy não está lá?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Roteiro da demo · commit f439a49 · arquivo `docs/roteiro-demo.md`
- Preciso explicar: o roteiro de 90 segundos, com as três abas, a animação e as notas honestas (nenhuma conversa da fila anexou foto; a tela reproduz o que o pipeline decidiu).
- Estudo: leia o roteiro e ensaie em voz alta com o cronômetro.
- Teste de compreensão: por que a frase "problemas resolvidos" deve ser trocada por "resolvidas sem pessoa"?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

### Cobertura (commits a4f7588 a 4b4c66c → tema)
| Arquivo | Tema |
|---|---|
| web/index.html | Tela GoResolve: o HTML e o desenho |
| web/styles.css, web/fonts/ | Tela GoResolve: o HTML e o desenho |
| web/app.js | O agente "ao vivo" é animação; Edição e decisão humana |
| web/render.js | O agente "ao vivo" é animação; Edição e decisão humana |
| web/render.test.js | Testes da tela |
| web/.vercelignore, web/.gitignore | Deploy estático na Vercel |
| docs/roteiro-demo.md | Roteiro da demo |
| 4b4c66c (grafia Belleza em 17 arquivos) | sem tema próprio: troca de texto; DIARIO.md tem a entrada |

## Fila e aprovação: motivo, lote, filtros e prazo · commit 0eeeb0a · arquivos `web/render.js` (`renderApprovals`, `prazoResposta`, `passaFiltro`), `web/app.js`
- Preciso explicar: por que rejeitar exige motivo (auditoria e aprendizado) e como o prazo sai do dado "SLA de primeira resposta" (≤ 240 min = atenção).
- Estudo: leia `prazoResposta` e rode `node --test web/render.test.js`.
- Teste de compreensão: um caso com "vencido há 30 min" aparece como? E um com 300 min restantes?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Painel de impacto e tempo poupado · commits d3f3f4d, 2dcef47 · arquivos `web/render.js` (`calcularImpacto`, `tempoPoupado`), `pipeline/export.py` (`tempo_referencia`), `schemas/resultado_publico.schema.json`
- Preciso explicar: de onde sai cada número (91% = 59 de 65 automáticas; ≈ 12 h = 59 × 12,2 min, média de `minutos_trabalhados` em 2.654 conversas de `tempo_por_conversa.csv`) e que o tempo poupado é estimativa.
- Estudo: leia `tempo_referencia()` e veja `tempo_referencia` em `web/data/results.json`.
- Teste de compreensão: por que a média vem do pipeline e não fica escrita à mão no JavaScript?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

## Ferramentas da atendente: encaminhar, respostas prontas, resolvido e CSV · commits d3f3f4d, 2dcef47 · arquivos `web/render.js` (`renderEncaminhar`, `RESPOSTAS_PRONTAS`, `renderResolvido`, `paraCsv`), `web/app.js`, `web/styles.css`, `web/index.html`
- Preciso explicar: tudo é simulado no navegador (`localStorage`); respostas prontas não prometem prazo, valor ou reembolso; CSV protegido contra fórmula.
- Estudo: leia `paraCsv` e `celula`; rode o teste "CSV protege fórmula".
- Teste de compreensão: o que acontece se um motivo começar com "=" ao abrir o CSV no Excel, e por quê?
- Status: [ ] li  [ ] rodei  [ ] explico em 30 s

### Cobertura (commits 0eeeb0a, d3f3f4d, 2dcef47 → tema)
| Arquivo | Tema |
|---|---|
| web/render.js, web/app.js | Fila e aprovação; Painel de impacto; Ferramentas da atendente |
| web/index.html, web/styles.css | Ferramentas da atendente (aba Impacto, estilos) |
| web/render.test.js | Testes da tela |
| pipeline/export.py, schemas/resultado_publico.schema.json | Painel de impacto e tempo poupado |
| web/data/results.json | Painel de impacto e tempo poupado (campo `tempo_referencia`) |
