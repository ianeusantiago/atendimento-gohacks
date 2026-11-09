# GoHacks Talent 2026: perguntas, slides e pitch

## 8. Modelos de slides, pitch e sabatina

### Slides (7, dentro do limite de 10)

| # | Título | Até 3 elementos |
|---|---|---|
| 1 | Nome e desafio | Nome, desafio, frase de valor |
| 2 | Dor | Pessoa, rotina, custo |
| 3 | Hoje | Fluxo em 3 ou 4 passos, com o gargalo em destaque |
| 4 | Solução | Frase, papel da IA, antes e depois |
| 5 | Demonstração | Print que serve de plano B |
| 6 | Impacto | Métrica de processo, métrica de negócio, método |
| 7 | Próximos passos | Dependência, passo de segunda-feira, piloto |

Deixe uma arquitetura de uma tela como slide reserva para a sabatina. Frase pronta do toolkit para adaptar: "Minha solução é [nome]: um agente de IA que [ação], para que [resultado]."

### Tempo do pitch

Só consegui ler a abertura na linha do tempo do toolkit (0:00–0:15). O restante é sugestão minha; ajuste ao que o site mostrar.

| Tempo | Conteúdo |
|---|---|
| 0:00–0:15 | Você, o projeto e o desafio |
| 0:15–1:00 | Pessoa com nome, rotina e custo |
| 1:00–1:30 | Solução em uma frase e transição para a demo |
| 1:30–3:30 | **Demo:** caso normal, depois o erro barrado pelo verificador |
| 3:30–4:30 | Antes e depois, e como você mediu |
| 4:30–5:00 | Primeira dependência e passo de segunda-feira |

Se faltar tempo, corte texto e preserve a demo.

### Perguntas para treinar

Responda em até 3 frases:

1. Como funciona tecnicamente?
2. Quem usaria isso na prática?
3. O que falta para funcionar de verdade?
4. Como medir o sucesso?
5. Por que precisa de IA aqui?
6. Onde sua IA errou e como você percebeu?
7. Que parte do código você sabe explicar sem ajuda?
8. O que acontece se o modelo errar em produção?
9. Quanto custa por caso e como isso escala?
10. Como seria com dados reais?
11. Por que essa arquitetura e não um único prompt?
12. O que você mudou depois do feedback?

Se não souber, use a saída do toolkit: "Não cheguei lá ainda, mas o próximo passo seria..."

**Regra de honestidade:** diga sempre "medi em N casos sintéticos" ou "é uma estimativa". Banca desconfia de ganho perfeito, e número sem método derruba a resposta seguinte.

## Prompt do pitch: siga este modelo de 4 minutos

Cole o prompt abaixo (Sonnet 5.5, esforço baixo) quando o produto do sábado estiver pronto. O roteiro de referência vem logo depois e é o modelo que eu quero.

```text
Escreva meu roteiro de pitch de 4 minutos para o GoHacks.
O MODELO É O ROTEIRO DE REFERÊNCIA COLADO ABAIXO. Siga exatamente a estrutura, a ordem, os tempos e o estilo dele:

1. Problema (0:00 a 0:35)
2. Hipótese e métricas (0:35 a 1:00)
3. Como funciona (1:00 a 1:50)
4. Prova (1:50 a 2:35)
5. Demo (2:35 a 3:25)
6. Próximos passos (3:25 a 4:00)

Regras de estilo, copiadas do modelo:
- Primeira pessoa, frases curtas, falado (não escrito). Começa com "Eu sou o Ian e resolvi...".
- O problema aparece com uma pessoa concreta e um número (ex.: "4 de 20 eram críticos", "12 dias sem resposta").
- A hipótese vem em uma frase e termina com duas métricas: a de processo (que eu medi) e a de negócio (que é próximo passo, se ainda não medi).
- "Como funciona" segue o padrão: a IA interpreta, a regra decide, o verificador confere. Diga o que o modelo NUNCA decide e por quê.
- "Prova" separa o que prova de verdade do que só mostra que nada quebrou. Diga o que NÃO foi medido e qual modelo foi medido.
- A demo é roteirizada passo a passo, termina com o personagem do início resolvido, e tem um momento em que o sistema BARRA algo.
- Os próximos passos incluem medir o que falta, dados reais, proteção de dados pessoais e humano conferindo no início.
- Termine com "Obrigado." Sem detalhe técnico além do que o modelo traz.

Regras de conteúdo:
- Use SOMENTE fatos, nomes e números do meu SPEC.md, do README e dos resultados em evals/. Não invente número, nome nem resultado.
- Onde faltar dado, escreva [A MEDIR] ou [A CONFIRMAR] e liste no fim o que preciso preencher.
- Mantenha cada bloco dentro do tempo (cerca de 130 palavras por minuto) e mostre a contagem de palavras por bloco.
- No fim, entregue: o roteiro, as 3 frases que eu mais devo ensaiar e as 3 perguntas mais prováveis da banca sobre este pitch, com resposta de até 3 frases.

ROTEIRO DE REFERÊNCIA (modelo):
<cole aqui o roteiro de 4 minutos abaixo>
```

### Roteiro de referência (4 minutos)

**1. Problema (0:00 a 0:35)**
"Eu sou o Ian e resolvi o pós-venda da Lumina. A fila mistura o simples com o sensível, e o crítico se perde. Nos 20 tickets da demo, 4 eram críticos: 2 de jurídico ou Procon, 1 de LGPD e 1 tentativa de manipulação. O Carlos ameaça processar, está há 12 dias sem resposta e ficou na posição 18, atrás de um 'oi'. E a Ana, a atendente, deveria revisar só exceções, mas lê tudo."

**2. Hipótese e métricas (0:35 a 1:00)**
"Minha hipótese: se o que os dados já respondem sai automático e correto, os críticos chegam primeiro à atendente. Defini duas métricas. A de processo, que eu medi: categoria, ação e pedido contra o gabarito. A de negócio, o tempo até a primeira resposta dos críticos, que é o próximo passo, porque os tickets não têm data de chegada."

**3. Como funciona (1:00 a 1:50)**
"A IA interpreta, a regra decide, o verificador confere. O ticket passa por cinco etapas. Pré-triagem, em código, separa a urgência. O Leitor, que é o Claude, entende o texto, inclusive em inglês e espanhol. Uma rede de segurança, feita de regras, lê o texto sozinha, e se achar um sinal crítico que o Leitor não viu, escala. O Juiz, em código, decide a ação com os dados do pedido, e o modelo nunca decide, porque o texto do cliente pode tentar manipular a decisão. O Redator monta a resposta só com fatos do pedido. E o Auditor barra reembolso, desconto, indenização e prazo novo."

**4. Prova (1:50 a 2:35)**
"Os números do repositório. Gabarito 23 de 23 e 25 de 25 casos novos, mas as regras foram escritas olhando esses dados, então prova que nada quebrou, não que generaliza. O número que vale: as regras sozinhas acertaram só 10 de 15 linhas em casos novos, e uma injeção virou resposta automática. Com uma IA local, o Ollama, a leitura acertou categoria em 21 de 23 e 22 de 25, e a ação ficou certa em 48 de 48. A leitura pelo Claude ainda não foi medida: é o primeiro passo."

**5. Demo (2:35 a 3:25)**
"Em vez de explicar, deixa eu mostrar. Seleciono 5 tickets abertos e vou para a fila. Abro o card do pedido 7009, três tickets de dois idiomas juntos. Digito 'vamos reembolsar'. O aprovar trava, porque o Auditor bloqueia. Encaminho para o jurídico e fecho. Lembra do Carlos? Agora ele é o primeiro."

**6. Próximos passos (3:25 a 4:00)**
"O que falta: medir o Claude nos mesmos casos, rodar com tickets reais e medir o tempo até a primeira resposta. Antes de ligar, mascaro nome, e-mail e telefone, porque o Leitor só precisa da intenção e do número do pedido. O status passa a vir do ERP, e nas primeiras semanas a atendente confere tudo. Obrigado."
