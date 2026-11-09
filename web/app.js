// Liga as duas telas ao DOM: Fila de entrada (lista + detalhe da conversa selecionada, com o
// log dentro) e Aprovação humana. Carrega data/results.json; se não existir, usa a amostra
// sintética data/results.sample.json e mostra um aviso. Decisões de aprovação e edições de
// resposta ficam só no localStorage deste navegador (sem efeito em servidor).
import { renderSummary, renderQueue, renderDetail, renderApprovals, renderRevisao, renderFiltros,
  filtroAtivo, podeEditar, temPii, renderImpacto, paraCsv, textoPronto } from "./render.js";

const STORAGE_KEY = "goresolve:decisoes:v1";
const EDITS_KEY = "goresolve:edicoes:v1";
const MOTIVOS_KEY = "goresolve:motivos:v1";
const ENC_KEY = "goresolve:encaminhamentos:v1";
const RESOLV_KEY = "goresolve:resolvidos:v1";
const $ = (sel) => document.querySelector(sel);

const state = { data: null, selected: null, decisions: {}, edits: {}, erros: {}, feitos: 0,
  motivos: {}, rejeitando: null, erroMotivo: "", selecionados: {}, filtro: {}, encs: {}, erroEnc: "", resolvidos: {} };

function readStore(key) {
  try {
    const raw = window.localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    $("#aviso-storage").hidden = false;
  }
}

async function fetchJson(url) {
  const resp = await fetch(url, { cache: "no-store" });
  if (!resp.ok) {
    const err = new Error(`${url}: HTTP ${resp.status}`);
    err.notFound = true;
    throw err;
  }
  try {
    return await resp.json();
  } catch {
    throw new Error(`${url} existe mas não é um JSON válido.`);
  }
}

async function loadData() {
  try {
    return { data: await fetchJson("data/results.json"), sample: false };
  } catch (err) {
    if (!err.notFound && !(err instanceof TypeError)) throw err;
  }
  return { data: await fetchJson("data/results.sample.json"), sample: true };
}

function showState(name, message) {
  for (const id of ["estado-carregando", "estado-erro", "app"]) {
    $(`#${id}`).hidden = id !== name;
  }
  if (name === "estado-erro" && message) $("#erro-detalhe").textContent = message;
}

function selectTab(name) {
  for (const btn of document.querySelectorAll("[role=tab]")) {
    const on = btn.dataset.tab === name;
    btn.setAttribute("aria-selected", String(on));
    btn.tabIndex = on ? 0 : -1;
    $(`#painel-${btn.dataset.tab}`).hidden = !on;
  }
}

function findItem(alias) {
  return state.data.itens.find((it) => it.alias === alias) || null;
}

function porPrioridade() {
  return [...state.data.itens].sort((a, b) => a.prioridade - b.prioridade);
}

function renderDetalhe() {
  clearInterval(replay);
  const it = state.selected;
  if (!it && state.feitos === 0) {
    $("#detalhe").innerHTML = `<p class="vazio">As ${state.data.itens.length} conversas estão na fila, ainda sem leitura. Aperte <strong>▶ Iniciar o agente</strong> para ver o agente ler e resolver uma por uma, da prioridade 1 à ${state.data.itens.length}.</p>`;
    return;
  }
  if (it && porPrioridade().indexOf(it) >= state.feitos) {
    $("#detalhe").innerHTML = `<p class="vazio">${it.alias} ainda está na fila: o agente não leu esta conversa.</p>`;
    return;
  }
  $("#detalhe").innerHTML = renderDetail(it, it ? state.edits[it.alias] ?? null : null, "",
    it ? state.decisions[it.alias] ?? null : null, it ? state.encs[it.alias] ?? null : null, state.erroEnc,
    it ? Boolean(state.resolvidos[it.alias]) : false);
}

// Só a aba de revisão é refeita ao salvar: os rascunhos não salvos das outras respostas ficam.
function renderRevisar(acabouDeMudar = null) {
  const f = state.feitos;
  const abertos = {};
  for (const ta of document.querySelectorAll("#revisar textarea[data-edicao]")) abertos[ta.dataset.edicao] = ta.value;
  $("#revisar").innerHTML = renderRevisao(state.data.itens, state.edits, state.erros, f);
  for (const ta of document.querySelectorAll("#revisar textarea[data-edicao]")) {
    const a = ta.dataset.edicao;
    // Mantém o que a pessoa digitou, salvo na resposta que acabou de ser salva ou restaurada.
    if (a in abertos && (a !== acabouDeMudar || state.erros[a])) ta.value = abertos[a];
  }
  const n = porPrioridade().slice(0, f).filter(podeEditar).length;
  $("#cont-revisar").textContent = n ? String(n) : "";
}

function render(recem = -1) {
  const itens = state.data.itens;
  const sel = state.selected ? state.selected.alias : null;
  const f = state.feitos;
  $("#resumo").innerHTML = renderSummary(itens, state.data.resumo, f);
  $("#fila").innerHTML = renderQueue(itens, sel, f, recem, state.filtro, state.resolvidos);
  renderDetalhe();
  renderAprovacoes();
  renderRevisar();
  renderImpactoTela();
  const pendentes = porPrioridade().slice(0, f).filter((it) => it.destino !== "automatico").length;
  $("#cont-aprov").textContent = pendentes ? String(pendentes) : "";
  const total = itens.length;
  $("#barra").style.width = `${(Math.min(f, total) / total) * 100}%`;
  $("#progresso-txt").textContent = f === 0 ? `0 de ${total} lidas` : `${Math.min(f, total)} de ${total} lidas`;
}

// Execução animada da fila: o agente lê uma conversa por vez, em ordem de prioridade.
const PASSO_MS = 180;
let execucao = null;

function terminar() {
  clearInterval(execucao);
  execucao = null;
  state.feitos = state.data.itens.length;
  $("#rodar").textContent = "↻ Rodar de novo";
  $("#rodar").disabled = false;
  $("#pular").hidden = true;
  render();
}

function iniciar() {
  clearInterval(execucao);
  const fila = porPrioridade();
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    state.selected = fila[0] || null;
    terminar();
    return;
  }
  state.feitos = 0;
  state.selected = null;
  $("#rodar").disabled = true;
  $("#pular").hidden = false;
  execucao = setInterval(() => {
    if (state.feitos >= fila.length) { terminar(); return; }
    state.feitos += 1;
    state.selected = fila[state.feitos - 1];
    render(state.feitos - 1);
    const linha = $(`.linha[data-alias="${CSS.escape(state.selected.alias)}"]`);
    if (linha) linha.scrollIntoView({ block: "nearest" });
  }, PASSO_MS);
}

function selecionar(alias) {
  state.selected = findItem(alias);
  state.erroEnc = "";
  render();
  selectTab("fila");
  // No celular o detalhe fica abaixo da lista: leva a pessoa até ele.
  if (window.matchMedia("(max-width: 860px)").matches) {
    $("#detalhe").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  $("#detalhe").focus({ preventScroll: true });
}

// Replay: acende um passo por vez. Com movimento reduzido, mostra tudo de uma vez.
let replay = null;
function tocar(alias) {
  clearInterval(replay);
  const passos = [...document.querySelectorAll(`[data-passos="${CSS.escape(alias)}"] .passo`)];
  const botao = document.querySelector(`[data-play="${CSS.escape(alias)}"]`);
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    passos.forEach((p) => p.classList.add("feito"));
    return;
  }
  passos.forEach((p) => p.classList.remove("feito", "ativo"));
  document.querySelector(`[data-passos="${CSS.escape(alias)}"]`).classList.add("tocando");
  if (botao) botao.disabled = true;
  let i = 0;
  const passo = () => {
    if (i > 0) passos[i - 1].classList.replace("ativo", "feito");
    if (i >= passos.length) {
      clearInterval(replay);
      if (botao) { botao.disabled = false; botao.textContent = "↻ Ver de novo"; }
      return;
    }
    passos[i].classList.add("ativo");
    i += 1;
  };
  passo();
  replay = setInterval(passo, 900);
}

function onClick(ev) {
  if (ev.target.closest("#rodar")) { iniciar(); return; }
  if (ev.target.closest("#pular")) { terminar(); return; }
  if (ev.target.closest("[data-baixar-csv]")) { baixarCsv(); return; }
  const resolver = ev.target.closest("[data-resolver], [data-reabrir]");
  if (resolver) {
    const alias = resolver.dataset.resolver ?? resolver.dataset.reabrir;
    const { [alias]: _, ...resto } = state.resolvidos;
    state.resolvidos = resolver.dataset.resolver ? { ...resto, [alias]: true } : resto;
    writeStore(RESOLV_KEY, state.resolvidos);
    render();
    return;
  }
  const inserir = ev.target.closest("[data-inserir-pronta]");
  if (inserir) {
    const caixa = inserir.closest(".bloco-edicao");
    const texto = textoPronto(caixa.querySelector("[data-pronta-sel]").value);
    const ta = caixa.querySelector("textarea");
    if (texto && ta) {
      ta.value = ta.value.trim() ? `${ta.value.trim()} ${texto}` : texto;
      ta.focus();
    }
    return;
  }
  const encaminhar = ev.target.closest("[data-encaminhar]");
  if (encaminhar) {
    const alias = encaminhar.dataset.encaminhar;
    const area = document.querySelector(`[data-enc-area="${CSS.escape(alias)}"]`).value;
    const nota = (document.querySelector(`[data-enc-nota="${CSS.escape(alias)}"]`).value || "").trim();
    if (nota.length < 5) state.erroEnc = "Escreva uma nota interna (pelo menos 5 caracteres).";
    else if (temPii(nota)) state.erroEnc = "A nota parece ter CPF, cartão ou telefone. Remova antes de encaminhar.";
    else {
      state.erroEnc = "";
      state.encs = { ...state.encs, [alias]: { area, nota } };
      writeStore(ENC_KEY, state.encs);
    }
    renderDetalhe();
    renderImpactoTela();
    return;
  }
  const desfEnc = ev.target.closest("[data-desfazer-enc]");
  if (desfEnc) {
    const { [desfEnc.dataset.desfazerEnc]: _, ...resto } = state.encs;
    state.encs = resto;
    writeStore(ENC_KEY, state.encs);
    renderDetalhe();
    renderImpactoTela();
    return;
  }
  const play = ev.target.closest("[data-play]");
  if (play) {
    tocar(play.dataset.play);
    return;
  }
  const decisao = ev.target.closest("[data-decisao]");
  if (decisao) {
    if (decisao.dataset.decisao === "rejeitar") {
      // Rejeitar exige motivo: abre o campo; a decisão só é registrada ao confirmar.
      state.rejeitando = decisao.dataset.alias;
      state.erroMotivo = "";
      renderAprovacoes();
      const campo = document.querySelector(`[data-motivo="${CSS.escape(state.rejeitando)}"]`);
      if (campo) campo.focus();
      return;
    }
    decidir(decisao.dataset.alias, decisao.dataset.decisao);
    return;
  }
  const confirmar = ev.target.closest("[data-confirmar-rejeicao]");
  if (confirmar) {
    const alias = confirmar.dataset.confirmarRejeicao;
    const motivo = (document.querySelector(`[data-motivo="${CSS.escape(alias)}"]`)?.value || "").trim();
    if (motivo.length < 5) {
      state.erroMotivo = "Escreva o motivo da rejeição (pelo menos 5 caracteres).";
      renderAprovacoes();
      return;
    }
    if (temPii(motivo)) {
      state.erroMotivo = "O motivo parece ter CPF, cartão ou telefone. Remova antes de confirmar.";
      renderAprovacoes();
      return;
    }
    state.motivos = { ...state.motivos, [alias]: motivo };
    writeStore(MOTIVOS_KEY, state.motivos);
    state.rejeitando = null;
    decidir(alias, "rejeitar");
    return;
  }
  if (ev.target.closest("[data-cancelar-rejeicao]")) {
    state.rejeitando = null;
    state.erroMotivo = "";
    renderAprovacoes();
    return;
  }
  if (ev.target.closest("[data-aprovar-lote]")) {
    const aprovados = Object.keys(state.selecionados).filter((a) => state.selecionados[a]);
    const novas = { ...state.decisions };
    for (const a of aprovados) novas[a] = "aprovar";
    state.decisions = novas;
    state.selecionados = {};
    writeStore(STORAGE_KEY, state.decisions);
    render();
    return;
  }
  if (ev.target.closest("[data-limpar-filtros]")) {
    state.filtro = {};
    $("#filtros").innerHTML = renderFiltros(state.filtro);
    render();
    return;
  }
  const desfazer = ev.target.closest("[data-desfazer]");
  if (desfazer) {
    const alias = desfazer.dataset.desfazer;
    const { [alias]: _, ...resto } = state.decisions;
    const { [alias]: __, ...motivos } = state.motivos;
    state.decisions = resto;
    state.motivos = motivos;
    writeStore(STORAGE_KEY, state.decisions);
    writeStore(MOTIVOS_KEY, state.motivos);
    render();
    return;
  }
  const salvar = ev.target.closest("[data-salvar]");
  if (salvar) {
    const alias = salvar.dataset.salvar;
    const texto = salvar.closest(".bloco-edicao").querySelector("textarea").value.trim();
    let erro = "";
    if (!texto) {
      erro = "A resposta não pode ficar vazia.";
    } else if (temPii(texto)) {
      erro = "O texto parece ter CPF, cartão ou telefone. Remova antes de salvar.";
    } else {
      state.edits = { ...state.edits, [alias]: texto };
      writeStore(EDITS_KEY, state.edits);
    }
    state.erros = { ...state.erros, [alias]: erro };
    renderRevisar(alias);
    renderDetalhe();
    return;
  }
  const restaurar = ev.target.closest("[data-restaurar]");
  if (restaurar) {
    const alias = restaurar.dataset.restaurar;
    const { [alias]: _, ...resto } = state.edits;
    state.edits = resto;
    state.erros = { ...state.erros, [alias]: "" };
    writeStore(EDITS_KEY, state.edits);
    renderRevisar(alias);
    renderDetalhe();
    return;
  }
  const irRevisar = ev.target.closest("[data-ir-revisar]");
  if (irRevisar) {
    selectTab("revisar");
    const alvo = document.querySelector(`#painel-revisar [data-edicao="${CSS.escape(irRevisar.dataset.irRevisar)}"]`);
    if (alvo) { alvo.scrollIntoView({ block: "center" }); alvo.focus({ preventScroll: true }); }
    return;
  }
  const linha = ev.target.closest("[data-alias]");
  if (linha) {
    selecionar(linha.dataset.alias);
    return;
  }
  const tab = ev.target.closest("[role=tab]");
  if (tab) selectTab(tab.dataset.tab);
}

function renderImpactoTela() {
  $("#impacto").innerHTML = renderImpacto(state.data.itens, state.decisions, state.encs, state.feitos,
    state.resolvidos, state.data.tempo_referencia ?? null);
}

function baixarCsv() {
  const csv = paraCsv(state.data.itens, { decisions: state.decisions, edits: state.edits,
    motivos: state.motivos, encs: state.encs, resolvidos: state.resolvidos });
  // BOM para o Excel abrir os acentos certos.
  const url = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "goresolve-fila.csv";
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function decidir(alias, valor) {
  state.decisions = { ...state.decisions, [alias]: valor };
  const { [alias]: _, ...sel } = state.selecionados;
  state.selecionados = sel;
  writeStore(STORAGE_KEY, state.decisions);
  render();
}

function renderAprovacoes() {
  $("#aprovacoes").innerHTML = renderApprovals(state.data.itens, state.decisions, state.edits,
    state.feitos, { motivos: state.motivos, rejeitando: state.rejeitando,
      erroMotivo: state.erroMotivo, selecionados: state.selecionados });
}

// Filtros (digitação e seleção) e caixas de seleção da aprovação em lote.
function onInput(ev) {
  const campo = ev.target.closest("[data-filtro]");
  if (campo) {
    state.filtro = { ...state.filtro, [campo.dataset.filtro]: campo.value };
    $("#fila").innerHTML = renderQueue(state.data.itens, state.selected?.alias ?? null, state.feitos, -1, state.filtro, state.resolvidos);
    const limpar = $("#filtros [data-limpar-filtros]");
    if (Boolean(limpar) !== filtroAtivo(state.filtro)) {
      // Atualiza só o botão "Limpar filtros", sem recriar o campo em que a pessoa digita.
      const tmp = document.createElement("div");
      tmp.innerHTML = renderFiltros(state.filtro);
      const novo = tmp.querySelector("[data-limpar-filtros]");
      if (limpar) limpar.remove(); else if (novo) $("#filtros .filtros").append(novo);
    }
    return;
  }
  const todos = ev.target.closest("[data-selecionar-todos]");
  if (todos) {
    const lidos = porPrioridade().slice(0, state.feitos);
    state.selecionados = {};
    if (todos.checked) {
      for (const it of lidos) {
        if (it.destino === "aprovacao" && !state.decisions[it.alias]) state.selecionados[it.alias] = true;
      }
    }
    renderAprovacoes();
    return;
  }
  const um = ev.target.closest("[data-selecionar]");
  if (um) {
    state.selecionados = { ...state.selecionados, [um.dataset.selecionar]: um.checked };
    renderAprovacoes();
  }
}

// Setas para cima e para baixo navegam pela fila (fora de campos de texto).
function onKey(ev) {
  if (!["ArrowDown", "ArrowUp"].includes(ev.key)) return;
  if (ev.target.closest("input, textarea, select") || $("#painel-fila").hidden) return;
  const visiveis = [...document.querySelectorAll("#fila .linha:not(.pendente)")].map((b) => b.dataset.alias);
  if (!visiveis.length) return;
  ev.preventDefault();
  const atual = visiveis.indexOf(state.selected?.alias);
  const prox = ev.key === "ArrowDown" ? Math.min(atual + 1, visiveis.length - 1) : Math.max(atual - 1, 0);
  selecionar(visiveis[atual === -1 ? 0 : prox]);
  const linha = document.querySelector(`.linha[data-alias="${CSS.escape(visiveis[atual === -1 ? 0 : prox])}"]`);
  if (linha) { linha.scrollIntoView({ block: "nearest" }); linha.focus({ preventScroll: true }); }
}

async function main() {
  showState("estado-carregando");
  document.addEventListener("click", onClick);
  document.addEventListener("input", onInput);
  document.addEventListener("change", onInput);
  document.addEventListener("keydown", onKey);
  try {
    const { data, sample } = await loadData();
    if (!data || !Array.isArray(data.itens)) {
      throw new Error("O arquivo não segue o contrato: falta a lista \"itens\".");
    }
    state.data = data;
    state.decisions = readStore(STORAGE_KEY);
    state.edits = readStore(EDITS_KEY);
    state.motivos = readStore(MOTIVOS_KEY);
    state.encs = readStore(ENC_KEY);
    state.resolvidos = readStore(RESOLV_KEY);
    $("#filtros").innerHTML = renderFiltros(state.filtro);
    state.selected = null; // abre com a fila ainda não lida; o agente começa no botão
    $("#banner-amostra").hidden = !sample;
    render();
    selectTab("fila");
    showState("app");
  } catch (err) {
    showState("estado-erro", String(err && err.message ? err.message : err));
  }
}

main();
