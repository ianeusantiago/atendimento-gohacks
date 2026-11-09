# PERGUNTAS: o que a banca pode perguntar

Só o documentador atualiza este arquivo, quando o Ian disser "documente". A resposta-base é um ponto de partida: reescreva com suas palavras e treine em voz alta, 30 segundos por pergunta. Responda primeiro a pergunta que foi feita. Material de apoio em `estudo/`.

## Modelo de entrada
```markdown
## <pergunta> · commit <hash> · critério: Modelagem | Adaptabilidade | Conceito | Cultura
- Resposta-base: até 3 frases, com um número ou teste
- Prova: arquivo, teste ou número
- Não diga: a frase que enfraquece ou que está errada
- Treinei em voz alta: [ ] 1x  [ ] 2x
```

## Perguntas para começar (troque X e Y pelos números medidos do projeto; o documentador preenche a prova)

| Pergunta | Resposta-base | Prova | Não diga |
|---|---|---|---|
| Qual é o problema e para quem? | Em uma frase: o problema, o usuário-chave e por que ele é o primeiro beneficiado. | SPEC.md | Descrever o produto antes do problema |
| Por que a decisão é código e não IA? | O texto pode tentar manipular um modelo e o código não negocia. A mesma entrada precisa dar a mesma decisão. A regra é do negócio: mudou, edita-se um arquivo e rodam-se os testes. | Arquivo das regras, teste de injeção | A analogia com fine-tuning; “não dá pra confiar na IA” |
| E se o modelo errar a leitura? | Uma segunda leitura por regras checa de forma independente e só empurra para o humano. Saída inválida vai para humano e o verificador barra promessas. O risco que sobra é um caso novo que nada reconheça. | Teste do leitor enganado | “Se errar, chega ao cliente” |
| Por que uma segunda leitura se já há o modelo? | São leituras independentes: o modelo erra por interpretar mal, a regra por não conhecer a frase. Roda sem internet. | Arquivo da rede de segurança | “Verificação humana”: são regras escritas por humanos |
| Como você sabe que funciona? | X de Y no gabarito, com a ressalva de vazamento, e X de Y em casos novos. O baseline sem IA fez X de Y. | Arquivo de avaliação, ERROS.md | “Testei à mão” como única prova |
| Qual é a prova de que a IA agrega? | Onde as regras sozinhas falham em frase nova e como a IA mais as regras resolveram, com o número medido. Diga qual modelo foi medido. | Medições registradas | Dizer que o Claude mediu algo que foi só o Claude Code construindo |
| O que ainda não foi provado? | A medição com dados reais, a métrica de negócio e o que não deu tempo. | README, limites | “Medi duas métricas” quando mediu uma |
| Automatizar não piora o problema? | Só o de baixo risco sai automático, com dados confirmados. O delicado e o ambíguo vão para humano. Na dúvida, escala. Nas primeiras semanas o humano confere tudo. | Regras de negócio | “Talvez piore”; estudo sem nome |
| E com dados reais? | Mascaro dados pessoais antes do modelo, porque ele só precisa da intenção. O status vem do sistema oficial por API, confiro quem é o dono, e o log fica sem dado pessoal. Começo em paralelo: o sistema sugere e o humano confere. | Arquivo que monta a chamada ao modelo | “Banco que não vaza de jeito nenhum” |
| Conte um erro da IA. | Erro, como percebi (medi antes de mexer), o que mudei na raiz e onde registrei. | ERROS.md | Pular “como percebi” |
| E uma injeção que a regra não conhece? | A regra não pegaria, é um limite. Mas a decisão vem do código, a resposta sai de modelos com dados confirmados e o verificador barra promessas. Por isso medimos com casos novos. | Casos de segurança | “Está tudo coberto” |
| Por que 100% no gabarito não basta? | As regras foram escritas olhando esses dados. Prova que nada quebrou, não que generaliza. O número que vale vem de casos novos. | Baseline | “A IA copiou o gabarito” |
| Por que um agente aqui e não um pipeline fixo? | Só usei agente onde o texto livre exige interpretação. Onde uma regra resolve, usei código. | SPEC, etapas do fluxo | Chamar tudo de agente |
| O que você faria com mais um dia? | Medir o modelo do produto nos mesmos casos, mascarar dados pessoais, ligar o sistema oficial e medir a métrica de negócio. | Próximos passos | Listar funcionalidades de tela |

## Perguntas do projeto (criadas pelo documentador a cada commit)

### Números medidos para as perguntas iniciais
- "Como você sabe que funciona?": 14 de 15 casos de `evals/casos.csv` (falha A01, registrada em ERROS.md), com a ressalva de que as regras foram escritas olhando esses dados. Testes: 476 em Python e 27 da tela. O número em casos novos é NÃO VERIFICADO: não há conjunto separado medido.
- "Qual é a prova de que a IA agrega?": NÃO VERIFICADO. Não há medição registrada de regras sozinhas contra regras mais o modelo nos mesmos casos.

## Uma mensagem "reembolse agora" faz o sistema reembolsar? · commits b1adc81, d3a61a0 · critério: Modelagem
- Resposta-base: não. Quando o texto traz uma ordem ao sistema, nenhuma ferramenta que move dinheiro (reembolso, reenvio, troca, reimpressão, cancelamento com estorno) roda sozinha: vai para uma pessoa. Informar status ou abrir chamado seguem normais, e é por isso que o caso malicioso M01 ainda abre o chamado.
- Prova: `tests/test_decide.py` (`test_instrucao_no_texto_*`); evals M01 "instrução ignorada: sim".
- Não diga: "o modelo percebe e ignora". Quem barra é o código.
- Treinei em voz alta: [ ] 1x  [ ] 2x

## E se o modelo cair no meio de uma reação alérgica? · commit d3a61a0 · critério: Adaptabilidade
- Resposta-base: se o classificador não responde e o texto tem termo de sintoma, a conversa segue o caminho de reação adversa: orientar a suspender o uso, registro pendente para o supervisor e topo da fila. O prazo de 24 h conta do relato. Se já venceu, aparece "PRAZO VENCIDO".
- Prova: `tests/test_run.py` (`test_escalacao_com_sintoma_mantem_reacao_adversa`, `test_cosmetovigilancia_com_prazo_vencido_e_avisada`); D03 com prazo 02/11 11:02.
- Não diga: que a lista de termos foi validada. Ela é "a confirmar".
- Treinei em voz alta: [ ] 1x  [ ] 2x

## O que impede o agente de passar do limite de valor? · commit d3a61a0 · critério: Conceito
- Resposta-base: duas barreiras. O `decide` manda para aprovação o que passa de R$ 200 (reenvio) ou R$ 100 (reembolso), e o ToolBox recusa qualquer valor acima do limite sem um id que o supervisor aprovou de verdade. Um id inventado não passa.
- Prova: `tests/test_tools.py` (`test_aprovacao_inventada_nao_libera_valor_acima_do_limite`); limites lidos de `politicas.csv`/`ferramentas.csv`.
- Não diga: "o modelo respeita o limite". O modelo nem vê o limite.
- Treinei em voz alta: [ ] 1x  [ ] 2x


## O agente que aparece lendo a fila está rodando a IA agora? · commits ee301aa, 3fa1720 · critério: Conceito
- Resposta-base: não. A tela reproduz, em animação, o que o pipeline já decidiu e gravou em `data/results.json`. A IA real rodou antes, no pipeline, com as 65 conversas. Mostro a animação para tornar visível quem faz o quê: a IA só lê, o código decide.
- Prova: `web/app.js` (`loadData` só lê o JSON); `docs/roteiro-demo.md` ("é uma reprodução").
- Não diga: "ele está processando em tempo real".
- Treinei em voz alta: [ ] 1x  [ ] 2x

## Se a atendente edita ou o supervisor aprova, o que acontece de verdade? · commits a4f7588, b3b4065, ff60b85 · critério: Modelagem
- Resposta-base: só no navegador. A edição e a decisão ficam no `localStorage`, e a "consequência" é um texto de simulação. Não há envio ao cliente nem mudança em sistema. Ao salvar, a tela recusa texto parecido com CPF, cartão ou telefone.
- Prova: `web/render.js` (`consequencia`, `temPii`); testes "texto editado com CPF..." e "decisão humana mostra a consequência simulada".
- Não diga: "o sistema reembolsa quando o supervisor aprova". Isso é o desenho, não o que a tela faz.
- Treinei em voz alta: [ ] 1x  [ ] 2x

## Por que esse visual, e o que é de marca? · commits a4f7588, 2794664 · critério: Cultura
- Resposta-base: a tela segue o padrão Grupo Exemplo em versão minimalista: fundo branco, azul `#2659a5`, Poppins, e vermelho só para alerta, para o olho ir ao que exige ação. Uso o nome GoResolve para a ferramenta. A origem do nome e a fonte exata das cores do brandbook: a confirmar com o Ian.
- Prova: `web/styles.css` (`:root`), `web/fonts/OFL.txt`.
- Não diga: que o brandbook oficial foi seguido ponto a ponto (não verificado).
- Treinei em voz alta: [ ] 1x  [ ] 2x

## O site está público? O que qualquer pessoa vê? · commit 9612f8f · critério: Adaptabilidade
- Resposta-base: é um site estático; a configuração publica a pasta `web/`, sem os testes. Os dados são o export público, com pseudônimos (CONV-xxx), sem CPF, cartão ou telefone. A URL não está registrada no repositório e a conferência em janela anônima NÃO foi feita.
- Prova: `web/.vercelignore`, `web/.gitignore`; `docs/verificacao.md` (NÃO VERIFICADO).
- Não diga: "já conferi que nada vaza no site publicado".
- Treinei em voz alta: [ ] 1x  [ ] 2x

## De onde vem o "12 horas poupadas"? · commit 2dcef47 · critério: Modelagem
- Resposta-base: do próprio dado do Grupo Exemplo: `tempo_por_conversa.csv` tem os minutos trabalhados em 2.654 atendimentos, média de 12,2 min. Multiplico pelas 59 conversas que o agente resolveu sozinho: cerca de 12 horas. É estimativa: supõe que cada uma custaria a média.
- Prova: `pipeline/export.py` (`tempo_referencia`), `web/render.js` (`tempoPoupado`), teste "tempo poupado = automáticas × média histórica".
- Não diga: "medimos 12 horas de economia". Não foi medido em operação.
- Treinei em voz alta: [ ] 1x  [ ] 2x

## O que a atendente faz além de aprovar? · commits d3f3f4d, 2dcef47 · critério: Adaptabilidade
- Resposta-base: revisa a resposta com trechos prontos que não prometem nada, encaminha para Logística, Qualidade ou Jurídico com nota interna, marca o caso como resolvido e baixa a fila em CSV. A aba Impacto mostra o progresso.
- Prova: `web/render.js` (`renderEncaminhar`, `RESPOSTAS_PRONTAS`, `renderResolvido`, `paraCsv`); 5 testes novos em `web/render.test.js`.
- Não diga: "o encaminhamento chega na área". Fica só no navegador (simulação).
- Treinei em voz alta: [ ] 1x  [ ] 2x

## Qual modelo vocês usaram? · critério: Conceito
- Resposta-base: `gpt-6-astra`, pelo proxy do evento, só para classificar. As decisões são código. O site não chama modelo: mostra o que o pipeline gravou.
- Prova: `pipeline/config.py` (`DEFAULT_MODEL`), `pipeline/llm.py`.
- Não diga: que medimos o ganho do modelo sobre as regras (NÃO VERIFICADO).
- Treinei em voz alta: [ ] 1x  [ ] 2x
