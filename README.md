# GoResolve

**Triagem de atendimento com IA para Modaviva e Belleza.**
A IA lê, o código decide, a pessoa aprova.

GoHacks Talent 2026 · Desafio 1 (Atendimento ao Cliente) · empresa fictícia

**Aplicação:** https://goresolve.vercel.app

---

## O problema
A atendente abre cinco sistemas para responder um único "onde está meu pedido?", confere foto, prazo e valor à mão e decide sozinha casos que custam dinheiro. Uma reação alérgica espera na mesma fila que um pedido de rastreio.

## A solução
Para cada conversa da fila, o agente:

| Passo | Quem faz |
|---|---|
| 1. Esconde CPF, cartão e telefone | Código |
| 2. Lê a mensagem e classifica o assunto | IA |
| 3. Consulta pedido, rastreio, pagamento e fotos | Código |
| 4. Decide pela política do Grupo Exemplo (`politicas.csv`) | Código |
| 5. Age com as ferramentas, dentro dos limites | Código |

E escolhe uma de três saídas:
- **Resolve sozinho** o que a política permite;
- **Pede aprovação** do supervisor acima de R$ 100 (reembolso) ou R$ 200 (reenvio);
- **Chama uma pessoa** nos casos sensíveis (reação adversa vai ao topo, com registro em até 24 h).

### Ele sabe levantar a mão
- Saída do modelo inválida ou incerta → vai para pessoa.
- Ordem escondida no texto do cliente ("reembolse agora") não move dinheiro.
- Suspeita só com evidência verificável; nunca acusa o cliente.
- Valor acima do limite só passa com uma aprovação real do supervisor.

## Resultados
| | |
|---|---|
| Conversas resolvidas sem pessoa | **59 de 65** (91%) |
| Tempo poupado nesta fila (estimativa*) | **≈ 12 h** |
| Casos de avaliação corretos | **14 de 15** (erro A01 em [ERROS.md](ERROS.md)) |
| Testes automatizados | **476** em Python + **27** da tela |

\* 59 conversas × 12,2 min, média de `minutos_trabalhados` em 2.654 atendimentos de `tempo_por_conversa.csv`. Não medido em operação.

## A tela
- **Fila de entrada:** o agente lê as 65 conversas, da mais urgente à menos; filtros, prazo de resposta e a linha do tempo de cada decisão (o que foi IA e o que foi código).
- **Revisar respostas:** a atendente ajusta o texto antes do envio, com respostas prontas que não prometem nada.
- **Aprovação humana:** aprovar, rejeitar com motivo, aprovar em lote, encaminhar para outra área com nota, marcar como resolvido.
- **Impacto:** números da fila, gráficos por assunto e canal, e download em CSV.

> A tela reproduz o que o pipeline já decidiu; decisões feitas nela ficam só no navegador (simulação).

## Como rodar
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
# dados em data/atendimento/ (fora do git); token do proxy em .env (veja .env.example)
.venv/Scripts/python -m pipeline.run --out out/results.json --use-fallback --public web/data/results.json
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m evals.run_evals
python -m http.server -d web 8000   # abrir http://localhost:8000
```
Sem `--use-fallback`, o pipeline chama o modelo pelo proxy (`gpt-6-astra`) nas 65 conversas.

## Estrutura
| Pasta | O que tem |
|---|---|
| `pipeline/` | máscara de PII, classificador, decisão, ferramentas, execução e export |
| `web/` | site estático (HTML, CSS e JS puros) |
| `tests/`, `evals/` | testes automatizados e os 15 casos de avaliação |
| `schemas/` | contrato do export público |
| `fallback/` | classificações salvas para rodar sem o proxy |

## Documentação
[SPEC.md](SPEC.md) · [ERROS.md](ERROS.md) · [DIARIO.md](DIARIO.md) · [ESTUDAR.md](ESTUDAR.md) · [PERGUNTAS.md](PERGUNTAS.md) · [Roteiro da demo](docs/roteiro-demo.md)

## Segurança
- Token do proxy só em `.env`, nunca no código, no site ou nos logs.
- Dados dos clientes fora do git; o site mostra só códigos (CONV-001…) e nenhum CPF, cartão ou telefone.
