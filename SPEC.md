# SPEC: agente de triagem de atendimento (GoHacks Talent 2026, Desafio 1)

Base: `docs/superpowers/specs/2026-11-07-atendimento-agente-design.md` e `docs/baseline.md`.

## Problema
Modaviva e Belleza atendem cerca de 130 conversas por dia (WhatsApp, e-mail, Reclame Aqui). Cada uma passa por vários sistemas quase à mão. Custo por conversa: R$ 4,80 (whatsapp), R$ 7,20 (e-mail), R$ 42,00 (Reclame Aqui), lidos de `politicas.csv`. Manchete: separar avaria falsa de verdadeira, resolvendo sozinho o que a política permite.

## Quem é afetado
Hipótese: atendente e supervisor da central, o cliente com reclamação verdadeira e a empresa. Usuário-chave: **a confirmar** (o Ian decidiu que não bloqueia agora).

## Fluxo atual
Atendente abre a conversa, classifica com tag, consulta ERP, transportadora, gateway, trocas e cupons, decide dentro da alçada (atendente: reenvio até R$ 200, reembolso até R$ 100) ou pede aprovação ao supervisor. Baseline medido: média de 10,0 min (whatsapp), 12,1 (e-mail) e 22,3 (Reclame Aqui) por conversa; 330 de 2.984 conversas do histórico sem tag.

## Fluxo proposto
Modelo classifica e extrai sinais; código consulta dados, aplica política e escolhe a ação (decisão de negócio é do código); saída validada por schema; incerto, sensível ou suspeito vai para pessoa. Suspeita nunca é acusação: só sinaliza ao supervisor, com evidência.

## Métricas
- Conversas da fila resolvidas sozinhas vs. enviadas para pessoa (contagens sobre as 65).
- Acerto da classificação e da ação nos casos de `evals/casos.csv`.
- Zero ações acima da alçada sem aprovação; zero vazamento de CPF, cartão ou telefone.
- Referência: fila de 65 (24 reclame_aqui, 22 email, 19 whatsapp; 59 abertas, 6 pendentes).

## Fora do escopo
Decisão de negócio no modelo; IA ao vivo na tela (versão 1); `notificar_clientes` e `abrir_incidente` em escala antes da avaria funcionar; extrapolar para o volume cheio; acusar cliente de fraude.

## Demo de 90 s
0:00 problema; 0:20 afetados; 0:35 solução; 1:00 prova com três casos (resolvido sozinho, enviado com evidência, suspeito sinalizado sem acusar); 1:20 resultado (quantas resolvidas, quantas para pessoa). Limite conhecido: nenhuma das 65 da fila tem foto, então avaria sem foto vira `solicitar_foto`; o caminho de suspeita é provado com casos do histórico.

## Premissas a confirmar
- Usuário-chave: a confirmar com o mentor. Hipótese: atendente e supervisor da central.
- Acesso ao ambiente do evento (API ou SDK): a confirmar.
- Como a banca avalia (pelo pitch): a confirmar.
- Extrapolar a amostra de 1 em 4 clientes para o volume cheio: a confirmar.
- Mapeamento de `reacao_adversa` e `erro_personalizacao` (sem tag em `politicas.csv`) para a lista de tags: a confirmar.
- Taxa de reabertura: o histórico não tem status `reaberto`; como medir: a confirmar.
