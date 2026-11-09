# Baseline e perfil dos dados

Fonte: `py scripts/profile.py` sobre `data/atendimento/` (saída real, medida em 2026-11-07).
Custos por conversa lidos de `politicas.csv` (seção `custo_por_conversa_rs`).

## Fila aberta (`fila_aberta.csv`)
| Medida | Contagem |
|---|---|
| Total | 65 |
| reclame_aqui | 24 |
| email | 22 |
| whatsapp | 19 |
| aberto | 59 |
| pendente | 6 |

## Baseline do histórico (`historico_conversas.csv`, 2.984 conversas)
| Canal | Conversas | Minutos trabalhados (média) | Custo por conversa (R$) |
|---|---|---|---|
| whatsapp | 1.963 | 10,0 | 4,80 |
| email | 675 | 12,1 | 7,20 |
| reclame_aqui | 346 | 22,3 | 42,00 |

- Custo total do histórico: R$ 28.814,40 (soma de conversas x custo do canal).
- Taxa de reabertura: 0,0%. Nenhuma das 2.984 conversas tem status `reaberto`; o histórico só traz resolvido (2.237), sem_resposta_cliente (404) e pendente (343). A taxa de reabertura por status não é mensurável aqui (a confirmar se há outra forma de medir).
- CSAT: 619 pesquisas respondidas, nota média 3,82.

## Problemas encontrados no histórico
| Problema | Contagem (de 2.984) |
|---|---|
| Conversas sem `tag_agente` | 330 |
| Tag fora das categorias de `politicas.csv`: "Outros" | 178 |
| Tag fora das categorias de `politicas.csv`: "Reclamação produto" | 104 |
| Conversas sem `order_id` (sem pedido) | 337 |

Observação: `reacao_adversa` e `erro_personalizacao` não têm `tag_equivalente` em `politicas.csv`; o mapeamento para a lista de tags é "a confirmar" (ver SPEC.md).

## Casos de avaliação (`evals/casos.csv`, 15 casos)
Composição: 8 normais, 4 difíceis, 2 ambíguos, 1 malicioso. Só IDs e rótulos vão para o arquivo; nenhum texto de cliente, CPF ou telefone. `categoria_esperada` e `acao_esperada` são derivadas por mim da regra citada em `regra_politicas` (política em `politicas.csv`, ferramentas em `ferramentas.csv`); são o gabarito proposto e aguardam revisão do Ian. "Agora" = 02/11/2026 e feriados da política contam nos dias úteis.

Origem dos difíceis (medido nos CSVs):
| Caso | Conversa | Origem | Medição |
|---|---|---|---|
| D01 | CV000001 | historico | Anexo com `hash_perceptual` que também aparece em CV000005 (outro cliente e outro pedido); `exif_data_captura` (01/07) é anterior à data do pedido (25/07). Medido: 8 hashes se repetem entre pedidos diferentes e 10 anexos têm EXIF anterior ao pedido. Ação: `sinalizar_suspeita` (quem decide é o supervisor, regra `reclamacao_suspeita`). |
| D02 | CV000051 | fila | Gateway tem duas transações do mesmo pedido, boleto paga e cartão capturada, ambas R$ 118,80. Acima de R$ 100: `solicitar_aprovacao` (regra `cobranca_duplicada`). |
| D03 | CV000028 | fila | Relato de reação (alergia) a suplemento, pedido entregue com lote registrado. Regra `reacao_adversa`; `registrar_cosmetovigilancia` é só do supervisor, então o analista aciona pessoa. |
| D04 | CV000039 | fila | Mesmo cliente e pedido em 3 conversas (fila e histórico); marca Lótus, pedido R$ 199,80 dentro da campanha (>= R$ 129, 13/10 a 04/11) sem o brinde. Regra `item_faltante` (inclui brinde): exige foto, logo `solicitar_foto`. |

Observações:
- A fila não tem anexos, por isso o único difícil com foto (D01) é do histórico. Cobri hash repetido e EXIF fora da janela em um só caso; deixei de fora um segundo caso de foto (ex.: CV000007, hash repetido entre 3 clientes) para caber os outros três tipos exigidos pelo brief.
- Malicioso: existe uma conversa real com instrução ao agente no texto do cliente (M01, CV000006, histórico). Busca por padrões nas mensagens de clientes achou só essa. O pedido tem atraso de até 7 dias úteis, então o esperado é o da regra `atraso_entrega` (abrir chamado), ignorando a instrução.
- Ambíguos (A01 CV000066: duas intenções; A02 CV000048: pergunta sem política que a cubra): esperado `acionar_pessoa`. É escolha minha, a confirmar.
- Normais: N01 e N02 (rastreio dentro do prazo), N03 e N04 (atraso de 2 e 4 dias úteis), N05 (cancelado antes da separação), N06 (reembolso R$ 99,66, 6 dias após a entrega), N07 e N08 (endereço aberto antes da separação).

Convenção de `acao_esperada`: aceita uma lista separada por `;` (mesmo formato de `acoes_obrigatorias` em `politicas.csv`) quando a política exige mais de um passo. D03 espera `orientar_suspensao_uso;registrar_cosmetovigilancia`; o segundo passo é só do supervisor, então o pipeline o entrega a uma pessoa.

## Prazo prometido (`pipeline/deadlines.py`)
Regra de `politicas.csv` (`prazos_entrega`): data do pedido + preparo + SLA da transportadora (região pela UF), em dias úteis (segunda a sexta, fora `feriados_nacionais`), contando a partir do primeiro dia útil depois do pedido. Interpretação adotada: `add_business_days(data_pedido, preparo + SLA)` devolve o n-ésimo dia útil depois de `data_pedido` (o próprio dia do pedido não conta, sem hora de corte). Preparo: Modaviva com `personalizacao` preenchida = `modaviva_personalizado`; Modaviva sem = `modaviva_sem_personalizacao`; demais marcas de `pedidos.csv` (Belleza) = `belleza`.

Validação contra `data_prometida` (6.092 pedidos, todos com o campo preenchido), medida em 07/11/2026 por `tests/test_deadlines.py`:
| Interpretação | Coincide |
|---|---|
| Adotada (dia útil seguinte ao pedido, com feriados, preparo por marca/personalização) | 6.092 (100,00%) |
| Sem feriados | 5.011 (82,26%) |
| Preparo sempre 1 dia | 4.656 (76,43%) |
| Pedido após 14h conta do dia seguinte | 4.279 (70,24%) |
| Dia do pedido conta como dia 1 | 0 (0,00%) |

Observação: 01/05/2026 não está em `feriados_nacionais` e os dados concordam (não é tratado como feriado).

## Sinais de suspeita nos anexos (`pipeline/evidence.py`)
Regras em código, sem modelo, sobre os 382 anexos de `anexos_conversas.csv` (280 conversas do histórico; a fila não tem anexos). Medido em 07/11/2026 por `tests/test_evidence.py`, avaliando cada anexo contra o próprio pedido e contra todos os anexos.
| Sinal | Regra | Detectado |
|---|---|---|
| `hash_repetido` | mesmo `hash_perceptual` em anexo de outro cliente ou outro pedido (repetição no mesmo pedido não conta) | 8 de 8 hashes documentados acima (17 anexos) |
| `exif_fora_da_janela` | `exif_data_captura` anterior a `data_pedido` | 10 de 10 anexos documentados acima |
| `exif_software_edicao` | `exif_software` contém um nome da lista `SOFTWARE_EDICAO` (editor, photoshop, lightroom, snapseed, picsart, gimp, facetune) | 6 de 10 anexos com software preenchido: os 6 "Editor de Fotos do Galaxy". Os 4 "Fotos do iOS" (app de galeria) ficam de fora: a confirmar |
| `descricao_incoerente` | descrição visual cita número de outro pedido, ou nomeia um objeto sem nenhuma palavra (4+ letras) em comum com `descricao_produto`; descrições que começam por caixa/embalagem/itens não são julgadas | 6 anexos, todos também com hash repetido |

- Total: 23 anexos (23 conversas) com ao menos um sinal; os 10 de EXIF anterior e os 6 de descrição incoerente estão entre os 17 de hash repetido.
- EXIF vazio: 212 anexos sem data de captura, nenhum gera sinal de EXIF (WhatsApp remove os metadados; ausência nunca é suspeita).
- D01 (CV000001): `hash_repetido`, `exif_fora_da_janela` e `descricao_incoerente`; a decisão é `sinalizar_suspeita` (`tests/test_decide.py`).

Correção (revisão da Task 6): só `hash_repetido` e `exif_fora_da_janela` (sinais fortes) levam a `sinalizar_suspeita`; `exif_software_edicao` e `descricao_incoerente` apenas corroboram (um recorte no editor da galeria ou uma descrição genérica podem vir de cliente honesto). Medido por `tests/test_evidence.py`, anexo a anexo:
| Regra | Anexos que ela marca | Sem (outro) sinal forte | Com (outro) sinal forte |
|---|---|---|---|
| `hash_repetido` (forte) | 17 | 7 | 10 com EXIF anterior |
| `exif_fora_da_janela` (forte) | 10 | 0 | 10 com hash repetido |
| `exif_software_edicao` (fraco) | 6 | 6 (não sinalizam mais) | 0 |
| `descricao_incoerente` (fraco) | 6 | 0 | 6 |

Com a correção, 17 anexos (não mais 23) levam a `sinalizar_suspeita`; D01 continua sinalizado.

## Revisão do Ian nos casos (aplicada)
- Regra para históricos: o pipeline avalia o pedido e o pagamento na data da conversa (`data_abertura`), não no retrato de 02/11. Estado posterior (estorno concluído, status final do pedido) não pode entrar na decisão.
- D04 (CV000039): `acionar_pessoa`. O cliente já enviou foto em 27/10 e o reenvio OMS000613 foi do SKU KSH-5002, não do brinde GBT-9001; não pedir foto pela 3ª vez. Antes era `solicitar_foto`.
- N06 (CV000003) passa de normal a difícil (limite de 7 dias e cobrança duplicada já estornada); `acao_esperada` = acionar_pessoa, confirmado pelo Ian (ver proposta abaixo).
- A01 (CV000066): `validar_cupom;acionar_pessoa`. Cliente recorrente com 2 pedidos, cupom de primeira compra não se aplica; a ficha do APC-5004 não informa frequência de uso.
- A02 (CV000048): categoria `cupom_promocao`, ação `acionar_pessoa`. Não há política sobre desconto de Black Friday; não repetir o telefone da cliente.
- Totais: 7 normais, 5 difíceis, 2 ambíguos, 1 malicioso.

### Proposta N06
Confirmado pelo Ian: opção A (acionar_pessoa); motivo: duas devoluções de R$ 99,66 (R$ 199,32 no total) e a política não diz se o limite de R$ 100 vale por ação ou pela soma. Categoria secundária: cobranca_duplicada (sem coluna própria no CSV).
Medido (pedido PED000040, valor R$ 99,66, cartão): entregue em 03/08, conversa aberta em 09/08 23:59:58, ou seja 6 dias, dentro dos 7 de `arrependimento_cancelamento`. O gateway tem duas transações de R$ 99,66 criadas com 76 s de diferença (TRX00001421 capturada, TRX00001422). No retrato de 02/11 a TRX00001422 está estornada (EST000015, motivo cancelamento_cliente, solicitado 10/08 08:13, processado 13/08), mas na data da conversa nenhum estorno existia: havia cobrança duplicada em aberto e o pedido já entregue, com devolução pedida. Logo "já estornada" é informação posterior à conversa.
Proposta: categoria `arrependimento_cancelamento` (secundária `cobranca_duplicada`), regra `arrependimento_cancelamento`, `acao_esperada` = `acionar_pessoa`. Motivo: são dois estornos de R$ 99,66 cada (abaixo de R$ 100 individualmente, R$ 199,32 juntos) e a política não diz como somar duplicidade com arrependimento. Alternativa: `reembolsar;reembolsar`, se o Ian considerar cada estorno isolado. `negar_por_politica` não se aplica (6 dias, dentro do prazo).

## Contexto do pedido na data da conversa (Task 6b, medido)
Medido com `pipeline/asof.py` e `pipeline/context_rules.py` sobre as 2.706 conversas (fila + histórico) que têm pedido em `pedidos.csv` (2.163 pedidos distintos); fila em 02/11 08:00, histórico na `data_abertura`. Só contagens.
- `trocas_reenvios.csv`: 528 pedidos têm alguma linha (418 com tipo `reenvio`). Com reenvio (tipo `reenvio`) solicitado até a data de alguma conversa do pedido: 135 pedidos (149 contando troca e nova produção).
- Brinde de preço zero que nenhum reenvio anterior levou (regra do D04): 3 pedidos, 4 conversas (D04 CV000039 e a CV000013 são do mesmo pedido).
- Cobrança duplicada ainda em aberto na data da conversa (2 ou mais transações cobradas e nenhum estorno concluído e processado até aquele momento): 76 pedidos, 91 conversas; 13 dessas conversas têm `tag_agente` Cancelamento (como N06) e 46 Financeiro. No retrato de 02/11 só 14 pedidos ainda têm duplicidade em aberto, ou seja, avaliar pelo retrato esconderia a maior parte desses casos.
- Anexos na data da conversa (R6e, `pipeline/asof.anexos_ate`: anexos da própria conversa sempre, os de outras conversas só se enviados até a data). Dos 8 hashes repetidos entre clientes ou pedidos diferentes (critério de `hash_repetido`), os 8 continuam detectados em pelo menos uma conversa, mas as conversas com `hash_repetido` caem de 17 (retrato de 02/11) para 9: a conversa mais antiga de cada repetição ainda não podia ver a imagem posterior. D01 continua em `sinalizar_suspeita` pela data de captura anterior ao pedido (`exif_fora_da_janela`), sem `hash_repetido`.

## Execução da fila (`py -m pipeline.run --out out/results.json`)
Medido em 07/11/2026 (tabela atualizada pela correção 1, abaixo): 65 conversas de `fila_aberta.csv`, classificação real pelo AI proxy (`gpt-6-astra`, prompt v1), decisão e ferramentas em código (papel atendente). Saída: `out/results.json` (fora do git); classificações salvas em `fallback/classificacoes.json` (só id e campos derivados). `--use-fallback` reproduziu as mesmas decisões e chamadas, na mesma ordem.

| Ação decidida | Conversas |
|---|---|
| abrir_chamado_transportadora | 11 |
| solicitar_foto | 11 |
| informar_status | 8 |
| negar_por_politica | 6 |
| encerrar_conversa | 5 |
| responder_duvida | 5 |
| validar_cupom | 5 |
| reenviar_produto | 3 |
| solicitar_aprovacao | 3 |
| verificar_pagamento | 3 |
| acionar_pessoa | 1 |
| orientar_suspensao_uso;registrar_cosmetovigilancia | 1 |
| alterar_endereco | 1 |
| reimprimir_personalizacao | 1 |
| trocar_produto | 1 |
| Total | 65 |

- Para pessoa (`acionar_pessoa`): 2 (reação adversa CV000028, D03; brinde fora do reenvio CV000039, D04). Escaladas pelo classificador: 0. Falhas isoladas: 0.
- Chamadas ao modelo: 60 (as 5 conversas em que só o bot falou viram `sem_interacao` por regra, sem modelo). Tokens: 45.188 de prompt e 2.853 de completion.
- Chamadas pendentes: 11 (5 `validar_cupom` aguardando o código, 3 `reenviar_produto` aguardando a escolha do cliente entre reenvio e reembolso no atraso, 1 `alterar_endereco` com o endereço no texto do cliente, 1 `trocar_produto` aguardando a escolha do novo produto, 1 `registrar_cosmetovigilancia` para o supervisor).
- Casos de avaliação da fila: 8 de 10 com a ação esperada. A01 e A02 (ambíguos) saíram `validar_cupom`: o modelo deu confiança 0,99 e 0,97, acima de `CONFIANCA_MINIMA` (0,6), então a ambiguidade não virou pessoa.
- Correção 1 (rastreio parado, reexecutada só com `--use-fallback`, mesmas classificações, sem chamar o proxy): `Case.dias_uteis_sem_movimento` passou a vir de `rastreio_portais_transportadoras.csv` (último evento até o "agora", se não for entregue/extraviado). 1 conversa mudou de `informar_status` para `abrir_chamado_transportadora` (rastreio parado há 5 dias úteis); as demais 64 decisões não mudaram. Pendentes passaram de 10 para 11 (`trocar_produto` agora aguarda o produto novo). 6 conversas já tinham primeira resposta e ficaram sem SLA pendente na ordenação.
