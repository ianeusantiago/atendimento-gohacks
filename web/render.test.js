// Rodar: node --test web/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  escapeHtml,
  temPii,
  consequencia,
  prazoResposta,
  passaFiltro,
  renderFiltros,
  renderAgente,
  podeEditar,
  renderRevisao,
  summarize,
  renderSummary,
  renderQueue,
  renderDetail,
  renderApprovals,
  renderLog,
} from "./render.js";

const here = dirname(fileURLToPath(import.meta.url));
const load = (name) => JSON.parse(readFileSync(join(here, "data", name), "utf8"));
const sample = load("results.sample.json");
const realPath = join(here, "data", "results.json");

const PROIBIDAS = /fraude|golpe/i;

function allOutputs(data) {
  const outs = [renderSummary(data.itens, data.resumo), renderQueue(data.itens), renderApprovals(data.itens, {})];
  for (const it of data.itens) outs.push(renderDetail(it), renderLog(it));
  return outs;
}

test("summarize bate com o resumo da amostra", () => {
  assert.deepEqual(summarize(sample.itens), sample.resumo);
});

test("summarize bate com o resumo do results.json real (se existir)", { skip: !existsSync(realPath) }, () => {
  const real = load("results.json");
  const s = summarize(real.itens);
  assert.deepEqual(s, real.resumo);
  assert.equal(s.automaticas + s.aprovacao + s.pessoa + s.supervisor, s.total);
});

test("renderSummary avisa quando o resumo diverge dos itens", () => {
  assert.doesNotMatch(renderSummary(sample.itens, sample.resumo), /não bate/);
  const errado = { ...sample.resumo, automaticas: sample.resumo.automaticas + 1 };
  assert.match(renderSummary(sample.itens, errado), /não bate/);
});

test("renderQueue([]) mostra estado vazio", () => {
  assert.match(renderQueue([]), /Nenhuma conversa na fila/);
});

test("renderQueue ordena por prioridade", () => {
  const html = renderQueue([...sample.itens].reverse());
  const aliases = [...html.matchAll(/data-alias="([^"]+)"/g)].map((m) => m[1]);
  const esperado = [...sample.itens].sort((a, b) => a.prioridade - b.prioridade).map((i) => i.alias);
  assert.deepEqual(aliases, esperado);
});

test("renderDetail inclui dados e evidências", () => {
  const sup = sample.itens.find((i) => i.destino === "supervisor");
  const html = renderDetail(sup);
  for (const d of sup.dados) {
    assert.ok(html.includes(escapeHtml(d.rotulo)), d.rotulo);
    assert.ok(html.includes(escapeHtml(d.valor)), d.valor);
  }
  for (const ev of sup.evidencias) {
    assert.ok(html.includes(escapeHtml(ev.tipo)));
    assert.ok(html.includes(escapeHtml(ev.detalhe)));
  }
  assert.match(html, /Nada enviado ao cliente — caso na fila do supervisor/);
  assert.match(html, /Em análise pelo supervisor/);
});

test("escapa HTML vindo dos dados", () => {
  const item = {
    ...sample.itens[0],
    alias: "CONV-999",
    motivo: `<script>alert("x")</script> 'aspas' & "duplas"`,
    dados: [{ rotulo: "<b>r</b>", valor: `"><img src=x onerror=alert(1)>` }],
    log: [{ etapa: "<i>e</i>", resultado: "<script>", ms: 1 }],
  };
  const outs = [renderDetail(item), renderQueue([item]), renderApprovals([{ ...item, destino: "pessoa" }]), renderLog(item)];
  for (const html of outs) {
    assert.doesNotMatch(html, /<script>/);
    assert.doesNotMatch(html, /<img/);
    assert.doesNotMatch(html, /<b>r<\/b>/);
  }
  assert.ok(renderDetail(item).includes("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &#39;aspas&#39; &amp; &quot;duplas&quot;"));
  assert.equal(escapeHtml(`<a href='x'>&"`), "&lt;a href=&#39;x&#39;&gt;&amp;&quot;");
});

test("nenhuma saída contém palavras proibidas", () => {
  for (const html of allOutputs(sample)) assert.doesNotMatch(html, PROIBIDAS);
  for (const html of [renderQueue([]), renderDetail(null), renderLog(null), renderApprovals([])]) {
    assert.doesNotMatch(html, PROIBIDAS);
  }
  assert.doesNotMatch(readFileSync(join(here, "data", "results.sample.json"), "utf8"), PROIBIDAS);
  if (existsSync(realPath)) {
    for (const html of allOutputs(load("results.json"))) assert.doesNotMatch(html, PROIBIDAS);
  }
  for (const f of ["index.html", "app.js", "render.js"]) {
    assert.doesNotMatch(readFileSync(join(here, f), "utf8"), PROIBIDAS, f);
  }
});

test("aprovação lista só itens não automáticos, por prioridade", () => {
  const html = renderApprovals(sample.itens, {});
  const aliases = [...new Set([...html.matchAll(/data-alias="([^"]+)"/g)].map((m) => m[1]))];
  const esperado = sample.itens
    .filter((i) => i.destino !== "automatico")
    .sort((a, b) => a.prioridade - b.prioridade)
    .map((i) => i.alias);
  assert.deepEqual(aliases, esperado);
  for (const it of sample.itens.filter((i) => i.destino === "automatico")) {
    assert.ok(!html.includes(it.alias), it.alias);
  }
});

test("aprovação mostra a decisão registrada no navegador", () => {
  const alvo = sample.itens.find((i) => i.destino === "aprovacao");
  const html = renderApprovals(sample.itens, { [alvo.alias]: "aprovar" });
  assert.match(html, /Aprovado\.<\/strong> O supervisor aprovou/);
});

test("Aprovar/Rejeitar só para destino aprovacao; pessoa e supervisor têm ação neutra", () => {
  const por = (d) => sample.itens.find((i) => i.destino === d);
  const aprov = renderApprovals([por("aprovacao")], {});
  assert.match(aprov, /data-decisao="aprovar"/);
  assert.match(aprov, /data-decisao="rejeitar"/);
  const pessoa = renderApprovals([por("pessoa")], {});
  assert.doesNotMatch(pessoa, /data-decisao="(aprovar|rejeitar)"/);
  assert.match(pessoa, /Assumir caso/);
  const sup = renderApprovals([por("supervisor")], {});
  assert.doesNotMatch(sup, /data-decisao="(aprovar|rejeitar)"/);
  assert.match(sup, /Marcar como visto/);
  const marcado = renderApprovals([por("supervisor")], { [por("supervisor").alias]: "visto" });
  assert.match(marcado, /Marcado como visto\.<\/strong> O supervisor viu/);
});

test("supervisor com mensagem padrão: rótulo diz que não foi enviada", () => {
  const sup = { ...sample.itens.find((i) => i.destino === "supervisor"), resposta_cliente: "Sua solicitação está em análise." };
  assert.match(renderDetail(sup), /Mensagem padrão ao cliente \(não enviada; caso na fila do supervisor\)/);
  assert.doesNotMatch(renderDetail(sup), /<h4>Resposta ao cliente<\/h4>/);
  const auto = sample.itens.find((i) => i.destino === "automatico");
  assert.match(renderDetail(auto), /<h4>Resposta ao cliente<\/h4>/);
});

test("cartão de automáticas diz 'Resolvidas pelo agente'", () => {
  assert.match(renderSummary(sample.itens, sample.resumo), /card-automaticas[^]*Resolvidas pelo agente/);
});

test("renderLog avisa quando classificar não tem tempo medido", () => {
  const nota = /Tempos da etapa de classificação não são medidos neste modo \(respostas salvas\)/;
  const it = sample.itens[0];
  assert.doesNotMatch(renderLog(it), nota);
  const salvo = { ...it, log: it.log.map((r) => (r.etapa === "classificar" ? { ...r, ms: 0 } : r)) };
  assert.match(renderLog(salvo), nota);
});

test("renderLog mostra as etapas e o total", () => {
  const it = sample.itens[0];
  const html = renderLog(it);
  for (const r of it.log) assert.ok(html.includes(escapeHtml(r.etapa)));
  const total = it.log.reduce((a, r) => a + r.ms, 0);
  assert.ok(html.includes(`>${total}<`));
});

test("edição só antes do envio: aprovação e pessoa, nunca automático nem supervisor", () => {
  const base = { alias: "CONV-001", resposta_cliente: "Olá!", canal: "email", marca_grupo: "Modaviva",
    acao: "x", categoria: "y", regra: "z", motivo: "m", dados: [], evidencias: [], log: [] };
  const itens = ["aprovacao", "pessoa", "automatico", "supervisor"].map((destino, i) =>
    ({ ...base, alias: `CONV-00${i + 1}`, prioridade: i + 1, destino }));
  const aba = renderRevisao(itens);
  for (const it of itens) {
    assert.equal(podeEditar(it), it.destino === "aprovacao" || it.destino === "pessoa");
    assert.equal(aba.includes(`data-edicao="${it.alias}"`), podeEditar(it), it.destino);
    // o detalhe nunca tem editor: aponta para a aba de revisão
    assert.doesNotMatch(renderDetail(it), /<textarea/);
  }
  assert.match(renderDetail(itens[1]), /data-ir-revisar="CONV-002"/);
  assert.doesNotMatch(renderDetail(itens[2]), /data-ir-revisar/);
  const editado = renderRevisao(itens, { "CONV-002": "<b>novo</b>" }, { "CONV-001": "erro x" });
  assert.match(editado, /&lt;b&gt;novo&lt;\/b&gt;/);
  assert.match(editado, /Editada neste navegador/);
  assert.match(editado, /erro x/);
  assert.match(renderRevisao(itens, {}, {}, 0), /o agente não terminou a fila/);
});

test("texto editado com CPF, cartão ou telefone é recusado; anos não", () => {
  for (const s of ["cpf 123.456.789-09", "123456789-09", "4111 1111 1111 1111", "(11) 98765-4321"]) {
    assert.ok(temPii(s), s);
  }
  assert.ok(!temPii("pedido de 2026 2027, valor R$ 150,00"));
});
test("agente em ação: um passo por etapa do log, IA só em classificar, final com o destino", () => {
  const item = { alias: "CONV-009", destino: "aprovacao", acao: "solicitar_aprovacao",
    log: [{ etapa: "mascarar", resultado: "ok", ms: 0 }, { etapa: "classificar", resultado: "<x>", ms: 1 },
      { etapa: "decidir", resultado: "solicitar_aprovacao", ms: 0 }] };
  const html = renderAgente(item);
  assert.equal((html.match(/class="passo[ "]/g) || []).length, 4);
  assert.equal((html.match(/data-quem="ia"/g) || []).length, 1);
  assert.match(html, /pede aprovação/);
  assert.match(html, /&lt;x&gt;/);
});
test("decisão humana mostra a consequência simulada, com desfazer e passo no agente", () => {
  const it = { alias: "CONV-004", destino: "aprovacao", acao: "solicitar_aprovacao", canal: "email",
    acoes_secundarias: ["reembolsar"], dados: [{ rotulo: "Valor do pedido", valor: "R$ 155,81" }], log: [] };
  assert.match(consequencia(it, "aprovar"), /reembolsar de R\$ 155,81/);
  assert.match(consequencia(it, "rejeitar"), /negar_por_politica/);
  assert.match(consequencia({ ...it, acoes_secundarias: ["registrar_cosmetovigilancia"] }, "assumir"), /24 h/);
  assert.match(renderApprovals([it], { "CONV-004": "aprovar" }), /data-desfazer="CONV-004"/);
  assert.match(renderAgente(it, "aprovar"), /Supervisor aprovou/);
  assert.doesNotMatch(renderAgente(it), /passo-humano/);
});
test("fila antes do agente: conversas 'Na fila', sem destino; contadores só do que foi lido", () => {
  const html = renderQueue(sample.itens, null, 0);
  assert.equal((html.match(/Na fila</g) || []).length, sample.itens.length);
  assert.doesNotMatch(html, /destino-(automatico|aprovacao|pessoa|supervisor)/);
  const parcial = renderQueue(sample.itens, null, 1, 0);
  assert.equal((parcial.match(/Na fila</g) || []).length, sample.itens.length - 1);
  assert.match(parcial, /linha recem/);
  const resumo = renderSummary(sample.itens, sample.resumo, 0);
  assert.match(resumo, new RegExp(`card-total"><span class="card-num">${sample.itens.length}<`));
  assert.match(resumo, /card-automaticas"><span class="card-num">0</);
  assert.doesNotMatch(resumo, /não bate/);
  assert.match(renderApprovals(sample.itens, {}, {}, 0), /Nenhum caso/);
});
test("rejeitar pede motivo; motivo aparece na decisão; lote só para aprovação", () => {
  const it = { alias: "CONV-004", prioridade: 4, destino: "aprovacao", acao: "solicitar_aprovacao", canal: "email",
    categoria: "arrependimento_cancelamento", motivo: "m", resposta_cliente: "Olá!", acoes_secundarias: ["reembolsar"],
    dados: [], log: [] };
  const pessoa = { ...it, alias: "CONV-001", prioridade: 1, destino: "pessoa" };
  const aberto = renderApprovals([it], {}, {}, Infinity, { rejeitando: "CONV-004", erroMotivo: "falta" });
  assert.match(aberto, /data-motivo="CONV-004"/);
  assert.match(aberto, /data-confirmar-rejeicao="CONV-004"/);
  assert.match(aberto, /falta/);
  const rejeitado = renderApprovals([it], { "CONV-004": "rejeitar" }, {}, Infinity, { motivos: { "CONV-004": "sem foto <b>" } });
  assert.match(rejeitado, /Motivo: sem foto &lt;b&gt;/);
  const lote = renderApprovals([it, pessoa], {}, {}, Infinity, { selecionados: { "CONV-004": true } });
  assert.match(lote, /Aprovar selecionados \(1\)/);
  assert.match(lote, /data-selecionar="CONV-004"/);
  assert.doesNotMatch(lote, /data-selecionar="CONV-001"/);
  // a resposta que vai ao cliente aparece no cartão (a editada, se houver)
  assert.match(renderApprovals([it], {}, { "CONV-004": "Texto revisado" }), /Texto revisado[^]*editada pela atendente|editada pela atendente[^]*Texto revisado/);
});

test("prazo de primeira resposta e filtros da fila", () => {
  const com = (v) => ({ dados: [{ rotulo: "SLA de primeira resposta", valor: v }] });
  assert.equal(prazoResposta(com("já respondida")), null);
  assert.deepEqual(prazoResposta(com("vencido há 962 min")).nivel, "vencido");
  assert.equal(prazoResposta(com("120 min restantes")).nivel, "atencao");
  assert.equal(prazoResposta(com("1622 min restantes")).texto, "vence em 27 h");
  const it = { alias: "CONV-004", destino: "aprovacao", canal: "email", categoria: "arrependimento_cancelamento" };
  assert.ok(passaFiltro(it, { busca: "arrepend" }));
  assert.ok(passaFiltro(it, { busca: "conv-004", destino: "aprovacao", canal: "email" }));
  assert.ok(!passaFiltro(it, { canal: "whatsapp" }));
  const q = renderQueue([{ ...it, prioridade: 1, dados: [] }], null, Infinity, -1, { destino: "pessoa" });
  assert.match(q, /Nenhuma conversa com esses filtros/);
  assert.match(renderFiltros({ busca: "<x>" }), /value="&lt;x&gt;"/);
});
import { paraCsv, calcularImpacto, renderImpacto, renderEncaminhar, textoPronto, RESPOSTAS_PRONTAS } from "./render.js";

const itA = { alias: "CONV-001", prioridade: 1, canal: "email", marca_grupo: "Modaviva", categoria: "atraso_entrega",
  destino: "pessoa", acao: "acionar_pessoa", motivo: '=cmd "x"', resposta_cliente: "Oi",
  dados: [{ rotulo: "SLA de primeira resposta", valor: "30 min restantes" }] };
const itB = { ...itA, alias: "CONV-002", prioridade: 2, destino: "automatico", motivo: "ok", dados: [] };

test("CSV protege fórmula, escapa aspas e leva decisão e encaminhamento", () => {
  const csv = paraCsv([itB, itA], { decisions: { "CONV-001": "assumir" }, encs: { "CONV-001": { area: "logistica", nota: "ver rastreio" } } });
  const linhas = csv.split("\r\n");
  assert.equal(linhas.length, 3);
  assert.ok(linhas[1].startsWith('"CONV-001"'));
  assert.ok(linhas[1].includes(`"'=cmd ""x"""`));
  assert.ok(linhas[1].includes('"Caso assumido"') && linhas[1].includes('"Logística"'));
});

test("impacto conta automáticas, urgentes e tratados", () => {
  const m = calcularImpacto([itA, itB], {}, { "CONV-001": { area: "qualidade", nota: "nota" } });
  assert.equal(m.pctAuto, 50);
  assert.equal(m.urgentes, 1);
  assert.equal(m.decididos, 1);
  assert.match(renderImpacto([itA, itB], {}, {}, 1), /quando o agente terminar/);
});

test("encaminhar só em caso humano e respostas prontas sem promessa", () => {
  assert.equal(renderEncaminhar(itB), "");
  assert.match(renderEncaminhar(itA), /data-encaminhar="CONV-001"/);
  assert.match(renderEncaminhar(itA, { area: "juridico", nota: "<b>" }), /Jurídico.*&lt;b&gt;/s);
  assert.equal(textoPronto("x"), "");
  for (const [, , t] of RESPOSTAS_PRONTAS) assert.doesNotMatch(t, /reembols|estorno|\bdias?\b|R\$|garant/i);
});

import { tempoPoupado, renderResolvido } from "./render.js";

test("tempo poupado = automáticas × média histórica; sem referência, nada", () => {
  assert.equal(tempoPoupado([itA, itB], null), null);
  const t = tempoPoupado([itB, itB, itA], { media_minutos: 40, conversas: 10 });
  assert.equal(t.min, 80);
  assert.equal(t.texto, "1 h 20 min");
});

test("marcar como resolvido só em caso humano e aparece no impacto e no CSV", () => {
  assert.equal(renderResolvido(itB), "");
  assert.match(renderResolvido(itA), /data-resolver="CONV-001"/);
  assert.match(renderResolvido(itA, true), /data-reabrir/);
  assert.equal(calcularImpacto([itA, itB], {}, {}, { "CONV-001": true }).resolvidos, 1);
  assert.match(paraCsv([itA], { resolvidos: { "CONV-001": true } }), /"sim"/);
});
