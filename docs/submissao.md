# Submissão do hackathon (prazo 16h30)

## 1. Nome do projeto
GoResolve

## 2. Qual problema você resolveu?
A atendente da Modaviva e da Belleza abre cinco sistemas para responder um único "onde está meu pedido?", confere foto, prazo e valor à mão e decide sozinha casos que custam dinheiro. Uma reação alérgica espera na mesma fila que um rastreio. São 2.984 conversas no histórico e R$ 28.814,40 de custo de atendimento; no Reclame Aqui, R$ 42 por conversa. Errar custa nos dois sentidos: pagar o que não devia ou negar um direito.

## 3. Qual é a sua solução?
O GoResolve faz a triagem da fila. Para cada conversa: 1) esconde CPF, cartão e telefone; 2) a IA lê a mensagem e classifica o assunto; 3) o código consulta pedido, rastreio, pagamento e fotos; 4) decide pela política da Grupo Exemplo (politicas.csv); 5) age com as ferramentas. Resolve sozinho o que a política permite, pede aprovação acima de R$ 100 (reembolso) ou R$ 200 (reenvio) e chama uma pessoa nos casos sensíveis. Reação adversa vai ao topo, com registro em até 24 h. Na tela, a atendente vê o agente ler a fila, revisa respostas com trechos prontos, aprova ou rejeita com motivo, encaminha para outra área, marca como resolvido e baixa a fila em CSV.

## 4. Como você usou a IA?
No produto, um modelo (gpt-6-astra, pelo proxy do evento) só classifica a mensagem; a saída é validada por schema e, se inválida ou incerta, o caso vai para pessoa. Ação, limite e prazo são decididos por código. Ordem escondida no texto ("reembolse agora") não move dinheiro. Para construir, usei o Claude Code com agentes de análise, implementação, revisão e documentação. Conferi com 476 testes automatizados e 15 casos de avaliação (14 corretos; o erro A01 está registrado em ERROS.md). Revisões encontraram e corrigi falhas como prazo de 24 h contado da data errada e reação alérgica perdida quando o modelo falhava.

## 5. Qual o resultado ou impacto esperado?
Na fila de 65 conversas, 59 (91%) foram resolvidas sem pessoa, 3 aguardam aprovação e 3 foram para uma pessoa. Pela média histórica de 12,2 min por atendimento (tempo_por_conversa.csv), isso poupa cerca de 12 horas da equipe nesta fila; estimativa, não medida em operação. Casos graves deixam de esperar e o dinheiro só sai com regra ou aprovação.

## 6. Slides
PDF exportado do Canva (9 slides).

## 7. GitHub
https://github.com/ianeusantiago/goresolve

## 8. Aplicação publicada
https://goresolve.vercel.app

## Relatório individual (opcional)
1. Atendimento ao cliente: é onde a fila mistura caso grave com caso simples e cada erro custa dinheiro ou confiança.
2. Claude Code com agentes (análise, implementação, revisão, documentação) e um modelo pelo proxy só para classificar.
3. Contou o prazo de 24 h da data errada e perdia a reação alérgica quando o modelo falhava; percebi na revisão final e com testes, e corrigi na raiz (decide.py, run.py).
4. Decisão no código e não no modelo; deixei de fora envio real ao cliente, login e chat ao vivo.
5. Mediria regras sozinhas contra regras mais o modelo em casos novos e ligaria a API real em paralelo com a operação.
