# Agente de triagem de atendimento: design (GoHacks Talent 2026, Desafio 1)

Data: 2026-11-07 · Autor: Ian (decisões de produto) · Rascunho por Claude · Status: aguardando aprovação

## Intenção e por quê
Modaviva e Belleza recebem cerca de 4.000 conversas por mês (130 por dia) em WhatsApp, e-mail e
Reclame Aqui. Cada uma passa por vários sistemas (ERP, transportadoras, gateway, OMS de trocas,
cupons), quase tudo à mão. Parte das reclamações de avaria não procede, e errar custa nos dois
sentidos (reenviar falsa: 45% do valor do pedido; negar verdadeira: metade do LTV mais 30% de
chance de Reclame Aqui; sinalizar verdadeira: R$ 6 e até 24 h a mais).

A banca avalia pelo **pitch**. O pitch conta três coisas, nesta ordem: o problema, quem é afetado
e a solução. A **manchete é a avaria falsa vs. verdadeira**: o agente resolve sozinho o que a
política permite, e só manda para pessoa o que passa do limite, é sensível ou é suspeito.

Critérios da banca: Modelagem 40 (fluxo de ponta a ponta, autonomia, correção da IA),
Adaptabilidade 20 (dados fictícios bem usados e caminho para dados reais), Conceito 20,
Cultura 20 (feedback recebido e ajustes feitos).

## Quem é afetado (hipótese, a confirmar)
Atendente e supervisor da central, o cliente com reclamação verdadeira (espera) e a empresa
(custo por conversa de R$ 4,80 a R$ 42). Usuário-chave não confirmado com o mentor: vai ao
SPEC.md como "a confirmar". O Ian decidiu que isso não bloqueia agora.

## Objetivos
- Fluxo de ponta a ponta sobre as 65 conversas de `fila_aberta.csv`, com a avaria como fatia 1.
- Demo de 90 segundos: problema (0:00), afetados (0:20), solução (0:35), prova com três casos
  (resolvido sozinho, enviado com evidência, suspeito sinalizado sem acusar) (1:00), resultado
  (quantas resolvidas, quantas para pessoa) (1:20).
- Cada decisão mostra a evidência (o dado do pedido ou do anexo que a justificou).
- Limite conhecido da demo: nenhuma das 65 conversas da fila tem foto (`anexos_conversas.csv` não
  traz anexos da fila; as imagens chegam pelo `ver_anexos` durante o evento). Na fila, avaria sem
  foto vira `solicitar_foto`. O caminho de suspeita (hash repetido, EXIF, descrição incoerente) é
  construído e provado com casos reais do histórico em `evals/casos.csv`, não mostrado como
  decisão sobre a fila. O pitch deve dizer isso com clareza.
- Depois da avaria: rastreio, atraso, cancelamento, endereço, cobrança duplicada, reação adversa.

## Não objetivos
- Não tomar decisão de negócio no modelo. Ação, alçada e prazo são do código.
- Não rodar a IA ao vivo na tela na primeira versão (ver abordagem B).
- Não cobrir `notificar_clientes` nem `abrir_incidente` em escala antes de a avaria funcionar.
- Não otimizar para o volume cheio; o histórico é amostra de 1 em 4 clientes e extrapolar é
  premissa "a confirmar".

## Anti-objetivos (falha mesmo que funcione)
- Acusar o cliente de fraude, ou negar sozinho por suspeita.
- Reenviar ou reembolsar acima da alçada sem aprovação, ou agir em reclamação sinalizada.
- Repetir CPF, cartão ou telefone em resposta, log, documento ou no site publicado.
- Obedecer instrução escrita no texto de um cliente.
- Inventar pedido, prazo ou dado. Dizer que funciona sem evidência executada.

## Restrições
- Só os dados fornecidos, em `data/atendimento/` (fora do git). "Agora" = 02/11/2026 08:00.
- Regras lidas de `politicas.csv` e `ferramentas.csv`, nunca copiadas à mão no prompt. As
  ferramentas mantêm os nomes e parâmetros de `ferramentas.csv`, para plugar no ambiente do evento.
- Token do AI proxy só em `.env` (formato OpenAI, `gpt-6-astra`, ~250 req/min compartilhados).
  Nunca no código, no front-end nem nos logs. Mascarar CPF, cartão e telefone antes de enviar ao
  modelo (`politicas.csv`: `mascarar_antes_de_enviar_a_modelos`).
- Toda saída do modelo é validada por schema; inválida ou incerta vai para pessoa.
- Prazo: congelar funcionalidades às 14h30, enviar até 16h15.
- Ambiente: Python 3.15 via `py` (o atalho `python` está quebrado); Node 26.13.0 em
  `C:\Program Files\nodejs`, que ainda não está no PATH da sessão do Claude Code.
- O site publicado na Vercel é público: só pode conter dados derivados e mascarados.
  O repositório `ianeusantiago/atendimento-gohacks` deve ser tratado como público até o
  Ian dizer o contrário.

## Abordagens consideradas
- **A. Pipeline em Python, tela estática (escolhida pelo Ian).** O Python processa as 65
  conversas com o proxy e grava JSON; uma página estática na Vercel mostra fila, resultado com
  evidência, aprovação humana e log. Ganha: a demo não depende de rede nem do limite do proxy.
  Perde: a tela mostra rodadas reais gravadas, não IA ao vivo.
- **B. Python mais servidor em Node, IA ao vivo.** Mais impressionante, mais risco de deploy e
  de limite compartilhado. Fica como evolução de A se sobrar tempo antes das 14h30.
- **C. Tudo em TypeScript.** Uma linguagem, mas a parte de CSV fica mais pesada e ainda não se
  sabe se o ambiente do evento é API ou SDK.

## Decisões do Ian
- Abordagem A, com B só se sobrar tempo.
- Manchete: avaria falsa vs. verdadeira.
- Orquestração: 4 agentes (analista, construtor, verificador, documentador), no máximo 2 ativos,
  conforme `PROMPT-ORQUESTRADOR.md`. Sem plano B de documento.
- A forma de acesso ao ambiente do evento (API ou SDK) segue sem confirmação; o Ian espera API.
  O pipeline acessa dados e ferramentas só por uma interface `Gateway`, com implementação local
  em CSV agora; a implementação remota só é escrita quando o formato do ambiente for conhecido.
- Demo sobre as 65 da fila (opção A): sem usar o histórico para mostrar o suspeito na tela. O
  Ian escolheu isso sabendo que a fila não tem fotos.
- O repositório `ianeusantiago/atendimento-gohacks` é público (confirmado pelo Ian).

## Decisões de Claude (a conferir)
- Claude faz a ponte entre os agentes com subagentes da própria sessão (Sonnet 5.5 para o
  analista, Opus 5.5 para construtor e verificador, Haiku 5.5 para o documentador), porque não há
  ferramenta de agent team nesta sessão. Eles não conversam entre si; a comunicação passa por Claude.
- Fluxo da avaria no código: (1) o modelo classifica e extrai pedido e sinais de risco;
  (2) o código consulta pedido, anexos (`ver_anexos`: hash repetido, EXIF, descrição visual vs.
  produto do pedido) e histórico do cliente; (3) checa foto exigida, prazo de 7 dias corridos do
  recebimento e valor dentro da alçada; (4) escolhe: sem foto → `solicitar_foto`; coerente e até
  R$ 200 → `reenviar_produto`; acima → `solicitar_aprovacao`; incoerente → `sinalizar_suspeita`;
  sensível → `acionar_pessoa`.
- Ordem da fila: reação adversa e Reclame Aqui primeiro, depois SLA.
- Resultados na tela: só contagens sobre as 65, sem extrapolar para 130 por dia.
- "Incoerente" é regra em código, sem o modelo: hash repetido entre clientes ou pedidos
  diferentes, EXIF com data fora da janela do pedido ou com software de edição, descrição visual
  que não bate com o produto. O modelo não decide suspeita.
- Precedência: reação adversa ou caso sensível; depois reclamação sinalizada (suspende a ação);
  depois fora do prazo (7 dias corridos do recebimento, só se a data de recebimento é conhecida); depois sem foto; por fim alçada. Limites lidos de `politicas.csv`.
- Mascarar: pseudônimos estáveis por cliente. Como o repositório e o site são públicos, só
  entram no repositório e no deploy campos derivados e mascarados, sem texto livre de cliente.
  O verificador confere isso antes do envio.
- `ver_anexos` já devolve texto, então não é preciso visão. Suporte a saída estruturada do
  `gpt-6-astra`: testar no primeiro commit do pipeline.
- Tela de aprovação humana: mostra e guarda o clique só no navegador, sem efeito no servidor.
- Mapeamento provisório de `reacao_adversa` e `erro_personalizacao` para as tags, marcado como
  premissa "a confirmar" no SPEC.md.
- A pausa da Fase 1 para o Ian revisar os casos é bloqueante.
- Mapeamento das categorias de `politicas.csv` sem tag (`reacao_adversa`, `erro_personalizacao`)
  para as tags da lista: a confirmar.

## O que fica para o construtor
Estrutura de pastas e nomes dos schemas, formato exato dos JSON de resultado, como mascarar os
dados antes do modelo e antes de publicar, retentativas e espera por limite de requisições,
telas (fila, resultado com evidência, aprovação humana, log; estados de carregamento, erro e
vazio), `/fallback` para a demo e a seção Comandos do `CLAUDE.md` (só com comandos executados).

## Entregas por fase
1. Analista: `SPEC.md`, perfil dos dados, baseline (custo, minutos, CSAT, reabertura, repetição
   por pedido), 15 casos em `evals/casos.csv` (8 normais, 4 difíceis, 2 ambíguos, 1 com
   instrução maliciosa). Pausa para o Ian revisar.
2. Construtor: schemas, fluxo e telas da fatia de avaria; depois as outras categorias.
3. Verificador tenta provar que está errado; o construtor corrige o grave.
4. Depois das 14h30: só correções.
O documentador roda quando o Ian disser "documente".
