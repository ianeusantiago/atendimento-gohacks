// Funções puras de renderização (sem DOM): recebem dados do contrato público v1
// (schemas/resultado_publico.schema.json) e devolvem HTML em string. Todo texto vindo dos
// dados passa por escapeHtml antes de entrar no HTML.

const CANAIS = { whatsapp: "WhatsApp", email: "E-mail", reclame_aqui: "Reclame Aqui" };

const DESTINOS = {
  automatico: "Resolvido pelo agente",
  aprovacao: "Aguardando aprovação do supervisor",
  pessoa: "Encaminhado para pessoa",
  supervisor: "Em análise pelo supervisor",
};

const DECISOES = {
  aprovar: "Aprovado",
  rejeitar: "Rejeitado",
  assumir: "Caso assumido",
  visto: "Marcado como visto",
};

// Ação disponível na fila humana, por destino. Só "aprovacao" tem Aprovar/Rejeitar; pessoa e
// supervisor recebem uma ação neutra (a decisão de mérito não é desta tela).
const ACOES_HUMANAS = {
  aprovacao: [
    ["aprovar", "Aprovar", "btn-primario"],
    ["rejeitar", "Rejeitar", "btn-secundario"],
  ],
  pessoa: [["assumir", "Assumir caso", "btn-primario"]],
  supervisor: [["visto", "Marcar como visto", "btn-secundario"]],
};

export function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const e = escapeHtml;

function byPriority(items) {
  return [...items].sort((a, b) => a.prioridade - b.prioridade);
}

function canalBadge(canal) {
  return `<span class="badge badge-${e(canal)}">${e(CANAIS[canal] ?? canal)}</span>`;
}

function destinoBadge(destino) {
  return `<span class="badge destino-${e(destino)}">${e(DESTINOS[destino] ?? destino)}</span>`;
}

export function summarize(items) {
  const s = { total: items.length, automaticas: 0, aprovacao: 0, pessoa: 0, supervisor: 0 };
  for (const it of items) {
    if (it.destino === "automatico") s.automaticas += 1;
    else if (it.destino in s) s[it.destino] += 1;
  }
  return s;
}

const CARDS = [
  ["total", "Na fila", ""],
  ["automaticas", "Resolvidas pelo agente", ""],
  ["aprovacao", "Aguardam aprovação", ""],
  ["pessoa", "Com uma pessoa", ""],
  ["supervisor", "Com o supervisor", ""],
];

// Categoria em português legível (categorias de politicas.csv); desconhecida: troca _ por espaço.
const CATEGORIAS = {
  reacao_adversa: "Reação adversa", item_faltante: "Item faltante", atraso_entrega: "Atraso na entrega",
  arrependimento_cancelamento: "Arrependimento", onde_esta_pedido: "Onde está o pedido",
  erro_personalizacao: "Erro de personalização", avaria_vazamento: "Avaria ou vazamento",
  alteracao_endereco: "Alteração de endereço", pagamento_pendente: "Pagamento pendente",
  cobranca_duplicada: "Cobrança duplicada", troca_fragrancia: "Troca de fragrância",
  duvida_produto: "Dúvida sobre produto", cupom_promocao: "Cupom ou promoção", elogio: "Elogio",
  sem_interacao: "Sem interação", nao_classificada: "Não classificada",
};

export function rotuloCategoria(c) {
  if (CATEGORIAS[c]) return CATEGORIAS[c];
  const s = String(c ?? "").replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// Cartões de resumo calculados dos itens. Se `resumo` (vindo do arquivo) divergir, mostra aviso.
// feitos: quantas conversas (em ordem de prioridade) o agente já processou na execução animada.
export function renderSummary(items, resumo, feitos = Infinity) {
  const completo = feitos >= items.length;
  const s = summarize(completo ? items : byPriority(items).slice(0, feitos));
  s.total = items.length;
  if (!completo) resumo = null;
  const cards = CARDS.map(
    ([k, label, ajuda]) =>
      `<div class="card card-${k}"><span class="card-num">${s[k]}</span><span class="card-label">${e(label)}</span>${
        ajuda ? `<span class="card-ajuda">${e(ajuda)}</span>` : ""
      }</div>`
  ).join("");
  const diverge = resumo && CARDS.some(([k]) => resumo[k] !== s[k]);
  const aviso = diverge
    ? `<p class="aviso" role="alert">Atenção: o resumo gravado no arquivo não bate com a contagem dos itens. Os cartões mostram a contagem dos itens.</p>`
    : "";
  return `<div class="cards">${cards}</div>${aviso}`;
}

export function renderQueue(items, selecionado = null, feitos = Infinity, recem = -1, filtro = {}, resolvidos = {}) {
  if (!items || items.length === 0) {
    return `<p class="vazio">Nenhuma conversa na fila.</p>`;
  }
  const ativo = filtroAtivo(filtro);
  const rows = byPriority(items)
    .map((it, i) => {
      const feito = i < feitos;
      // Filtro só vale para o que o agente já leu (antes disso não há assunto nem destino).
      if (ativo && (!feito || !passaFiltro(it, filtro))) return "";
      const prazo = feito ? prazoResposta(it) : null;
      const relogio = feito && resolvidos[it.alias]
        ? `<span class="prazo prazo-ok">✓ resolvido</span>`
        : prazo
        ? `<span class="prazo prazo-${prazo.nivel}" title="Prazo de primeira resposta">${e(prazo.texto)}</span>`
        : "";
      // Antes de o agente ler, a conversa não tem assunto nem destino: só está na fila.
      return `<li>
  <button type="button" class="linha${feito ? "" : " pendente"}${i === recem ? " recem" : ""}" data-alias="${e(it.alias)}" aria-current="${it.alias === selecionado}">
    <span class="prio" title="Prioridade">${e(it.prioridade)}</span>
    <span class="alias">${e(it.alias)}</span>
    <span class="categoria" data-categoria="${e(it.categoria)}">${feito ? e(rotuloCategoria(it.categoria)) : "Aguardando leitura"}</span>
    <span class="direita">${feito ? destinoBadge(it.destino) : `<span class="badge destino-fila">Na fila</span>`}${relogio}</span>
  </button>
</li>`;
    })
    .filter(Boolean)
    .join("\n");
  if (!rows) return `<p class="vazio">Nenhuma conversa com esses filtros.</p>`;
  return `<ol class="fila">${rows}</ol>`;
}

// Barra de filtros da fila (valores atuais em `f`).
export function renderFiltros(f = {}) {
  const opt = (v, rot, atual) => `<option value="${v}" ${atual === v ? "selected" : ""}>${rot}</option>`;
  return `<div class="filtros" role="search">
  <input type="search" class="campo" placeholder="Buscar código ou assunto" aria-label="Buscar na fila" data-filtro="busca" value="${e(f.busca || "")}">
  <select class="campo" aria-label="Filtrar por destino" data-filtro="destino">
    ${opt("", "Todos os destinos", f.destino || "")}${opt("automatico", "Resolvido pelo agente", f.destino)}${opt("aprovacao", "Aguardando aprovação", f.destino)}${opt("pessoa", "Com uma pessoa", f.destino)}${opt("supervisor", "Com o supervisor", f.destino)}
  </select>
  <select class="campo" aria-label="Filtrar por canal" data-filtro="canal">
    ${opt("", "Todos os canais", f.canal || "")}${opt("reclame_aqui", "Reclame Aqui", f.canal)}${opt("email", "E-mail", f.canal)}${opt("whatsapp", "WhatsApp", f.canal)}
  </select>
  ${filtroAtivo(f) ? `<button type="button" class="link" data-limpar-filtros>Limpar filtros</button>` : ""}
</div>`;
}

function listaPares(pares, chaveA, chaveB, vazio) {
  if (!pares || pares.length === 0) return `<p class="muted">${e(vazio)}</p>`;
  return `<dl class="pares">${pares
    .map((p) => `<dt>${e(p[chaveA])}</dt><dd>${e(p[chaveB])}</dd>`)
    .join("")}</dl>`;
}

// Mesmos padrões de pipeline/mask.py (cartão, CPF, telefone): texto editado com PII não é salvo.
const PII = [
  /(?<![\w+])(?:\d{13,19}|\d{4}([ .-])\d{4}\1\d{4}\1\d{1,7}|\d{4}[ .-]\d{6}[ .-]\d{5})(?!\w)/,
  /(?<!\w)(?:\d{3}[.\s-]\d{3}[.\s-]\d{3}[-./\s]\d{2}|\d{9}-\d{2}|\d{11})(?!\w)/,
  /(?<!\w)(?:(?:\+?55[\s-]?)?\(?\d{2}\)?[\s-]?9?\d{4}[\s-]?\d{4}|9\d{4}[\s-]?\d{4}|(?!(?:19|20)\d\d[\s-](?:19|20)\d\d\b)\d{4}[\s-]\d{4})(?!\w)/,
];

export function temPii(texto) {
  return PII.some((re) => re.test(String(texto ?? "")));
}

// Só dá para editar antes de enviar: casos que aguardam aprovação ou pessoa. Automáticos já
// foram enviados; no supervisor nada é enviado até a decisão dele.
export function podeEditar(item) {
  return Boolean(item && item.resposta_cliente && (item.destino === "aprovacao" || item.destino === "pessoa"));
}

// No detalhe a resposta é só leitura; quem pode ser editada aponta para a aba "Revisar respostas".
function blocoResposta(item, editado) {
  if (!item.resposta_cliente) {
    return `<p class="muted">${item.destino === "supervisor" ? "Nada enviado ao cliente — caso na fila do supervisor." : "Nada enviado ao cliente."}</p>`;
  }
  if (!podeEditar(item)) {
    const nota = item.destino === "automatico"
      ? `<p class="nota">Enviada pelo agente. Não pode ser editada depois de enviada.</p>` : "";
    return `<blockquote class="resposta">${e(item.resposta_cliente)}</blockquote>${nota}`;
  }
  return `<blockquote class="resposta">${e(editado ?? item.resposta_cliente)}</blockquote>
<p class="nota">${editado != null ? "Editada neste navegador. " : "Ainda não enviada. "}<button type="button" class="link" data-ir-revisar="${e(item.alias)}">Revisar esta resposta</button></p>`;
}

// Editor de uma resposta (aba "Revisar respostas").
export function editorResposta(item, editado = null, erro = "") {
  const texto = editado ?? item.resposta_cliente;
  return `<div class="bloco-edicao">
<label class="rotulo-edicao" for="edicao-${e(item.alias)}">Rascunho antes do envio</label>
<textarea id="edicao-${e(item.alias)}" class="edicao" rows="4" data-edicao="${e(item.alias)}">${e(texto)}</textarea>
${renderProntas(item.alias)}
${erro ? `<p class="erro-edicao" role="alert">${e(erro)}</p>` : ""}
<div class="aprov-botoes">
  <button type="button" class="btn btn-primario" data-salvar="${e(item.alias)}">Salvar edição</button>
  ${editado != null ? `<button type="button" class="btn btn-secundario" data-restaurar="${e(item.alias)}">Restaurar texto do agente</button>` : ""}
</div>
${editado != null ? `<p class="nota">Editada neste navegador.</p>` : ""}
</div>`;
}

export function renderRevisao(items, edits = {}, erros = {}, feitos = Infinity) {
  const lista = byPriority(items || []).slice(0, feitos).filter(podeEditar);
  if (lista.length === 0) {
    return `<p class="vazio">Nenhuma resposta para revisar${feitos < (items || []).length ? " ainda: o agente não terminou a fila" : ""}.</p>`;
  }
  const rows = lista.map((it) => `<li class="aprov">
  <div class="aprov-info">
    <span class="prio" title="Prioridade">${e(it.prioridade)}</span>
    <button type="button" class="link" data-alias="${e(it.alias)}">${e(it.alias)}</button>
    <span class="categoria-cab">${e(rotuloCategoria(it.categoria))}</span>
    ${destinoBadge(it.destino)}
  </div>
  <p class="motivo">${e(it.motivo)}</p>
  ${editorResposta(it, edits[it.alias] ?? null, erros[it.alias] || "")}
</li>`).join("\n");
  return `<p class="nota">Respostas que ainda não saíram: revise antes do envio. A edição fica só neste navegador; não escreva CPF, cartão ou telefone.</p><ol class="aprovacoes">${rows}</ol>`;
}

// Passos do agente, na linguagem do pitch. "quem" mostra a divisão: a IA só lê; o código decide.
const PASSOS = {
  mascarar: ["Esconde dados pessoais", "Código", "CPF, cartão e telefone viram [CPF], [CARTAO], [TEL] antes de qualquer IA."],
  classificar: ["Lê a mensagem", "IA", "O modelo só interpreta: categoria, pedido citado e sinais de risco."],
  consultar_pedido: ["Consulta o pedido", "Código", "Status, entrega, rastreio, pagamento e fotos vêm dos dados, não da IA."],
  decidir: ["Decide pela política", "Código", "Regras de politicas.csv: prazo, foto, limite de valor, suspeita."],
  executar: ["Age com as ferramentas", "Código", "Chama só ferramentas permitidas ao atendente; o resto fica pendente."],
  falha: ["Falha isolada", "Código", "A conversa vai para uma pessoa e a fila continua."],
};

const FINAL = {
  automatico: "Resolvido sozinho",
  aprovacao: "Passou do limite: pede aprovação",
  pessoa: "Sensível ou fora da política: chama uma pessoa",
  supervisor: "Evidência a conferir: supervisor analisa",
};

// O que aconteceria depois da decisão humana. É simulação: o site não executa nada.
export function consequencia(item, decisao) {
  const valor = ((item.dados || []).find((d) => d.rotulo === "Valor do pedido") || {}).valor;
  const acao = (item.acoes_secundarias || [])[0];
  const cosmeto = (item.acoes_secundarias || []).includes("registrar_cosmetovigilancia");
  switch (decisao) {
    case "aprovar":
      return `O supervisor aprovou. O agente executa ${acao ? acao : "a ação"}${valor ? ` de ${valor}` : ""} com essa aprovação e avisa o cliente.`;
    case "rejeitar":
      return "O supervisor rejeitou. O agente responde ao cliente com a regra da política (negar_por_politica) e encerra a conversa.";
    case "assumir":
      return `A atendente assumiu: o caso sai da fila do agente e fica com ela.${cosmeto ? " O registro de cosmetovigilância segue pendente para o supervisor, em até 24 h." : ""}`;
    case "visto":
      return "O supervisor viu as evidências. Reenvio, troca e reembolso seguem suspensos até a decisão dele.";
    default:
      return "";
  }
}

const QUEM_DECIDIU = { aprovar: "Supervisor aprovou", rejeitar: "Supervisor rejeitou", assumir: "Atendente assumiu", visto: "Supervisor viu" };

export function renderAgente(item, decisao = null) {
  const passos = (item.log || []).map((r) => {
    const [titulo, quem, ajuda] = PASSOS[r.etapa] || [r.etapa, "Código", ""];
    return `<li class="passo" data-quem="${quem === "IA" ? "ia" : "codigo"}">
  <span class="passo-icone" aria-hidden="true"></span>
  <div><p class="passo-titulo" title="${e(ajuda)}">${e(titulo)} <span class="quem quem-${quem === "IA" ? "ia" : "codigo"}">${e(quem)}</span></p>
  <p class="passo-res">${e(r.resultado)}</p></div>
</li>`;
  });
  passos.push(`<li class="passo passo-final destino-bloco-${e(item.destino)}">
  <span class="passo-icone" aria-hidden="true"></span>
  <div><p class="passo-titulo">${e(FINAL[item.destino] ?? item.destino)}</p>
  <p class="passo-res"><code>${e(item.acao)}</code></p></div>
</li>`);
  if (decisao && QUEM_DECIDIU[decisao]) {
    passos.push(`<li class="passo passo-humano">
  <span class="passo-icone" aria-hidden="true"></span>
  <div><p class="passo-titulo">${e(QUEM_DECIDIU[decisao])} <span class="quem">Pessoa</span></p>
  <p class="passo-res">${e(consequencia(item, decisao))} <span class="muted">(simulação)</span></p></div>
</li>`);
  }
  return `<section class="agente">
  <div class="agente-cab">
    <h4>O agente em ação</h4>
    <button type="button" class="btn btn-primario" data-play="${e(item.alias)}">▶ Ver o agente agir</button>
  </div>
  <ol class="passos" data-passos="${e(item.alias)}">${passos.join("")}</ol>
</section>`;
}

export function renderDetail(item, editado = null, _erro = "", decisao = null, enc = null, erroEnc = "", resolvido = false) {
  if (!item) {
    return `<p class="vazio">Selecione uma conversa na fila para ver a decisão e a evidência.</p>`;
  }
  const secundarias =
    item.acoes_secundarias && item.acoes_secundarias.length
      ? `<dt>Ações seguintes</dt><dd>${item.acoes_secundarias.map((a) => `<code>${e(a)}</code>`).join(" ")}</dd>`
      : "";
  const catSec = item.categoria_secundaria
    ? `<dt>Categoria secundária</dt><dd>${e(item.categoria_secundaria)}</dd>`
    : "";
  const tituloResposta =
    item.destino === "supervisor"
      ? "Mensagem padrão ao cliente (não enviada; caso na fila do supervisor)"
      : "Resposta ao cliente";
  const resposta = blocoResposta(item, editado);
  return `<article class="detalhe">
  <header class="detalhe-cab">
    <h3>${e(item.alias)}</h3>
    <span class="categoria-cab">${e(rotuloCategoria(item.categoria))}</span>
    ${destinoBadge(item.destino)}
  </header>
  ${renderAgente(item, decisao)}
  <section>
    <h4>Por que</h4>
    <p class="motivo">${e(item.motivo)}</p>
  </section>
  <section>
    <h4>Dados que justificaram</h4>
    ${listaPares(item.dados, "rotulo", "valor", "Sem dados do pedido.")}
  </section>
  <section>
    <h4>Evidências</h4>
    ${listaPares(item.evidencias, "tipo", "detalhe", "Nenhuma evidência de anexo.")}
  </section>
  <section>
    <h4>${e(tituloResposta)}</h4>
    ${resposta}
  </section>
  ${renderResolvido(item, resolvido)}
  ${renderEncaminhar(item, enc, erroEnc)}
  <details class="log-detalhe">
    <summary>Detalhes técnicos e log</summary>
    <dl class="pares">
      <dt>Canal</dt><dd>${e(CANAIS[item.canal] ?? item.canal)} · ${e(item.marca_grupo)}</dd>
      <dt>Ação</dt><dd><code>${e(item.acao)}</code></dd>
      ${secundarias}
      <dt>Destino</dt><dd>${e(DESTINOS[item.destino] ?? item.destino)}</dd>
      <dt>Categoria</dt><dd>${e(item.categoria)}</dd>
      ${catSec}
      <dt>Regra (politicas.csv)</dt><dd><code>${e(item.regra)}</code></dd>
    </dl>
    ${renderLog(item)}
  </details>
</article>`;
}

// opts: motivos {alias: texto da rejeição}, rejeitando (alias com o campo de motivo aberto),
// erroMotivo, selecionados {alias: true} para aprovação em lote.
export function renderApprovals(items, decisions = {}, edits = {}, feitos = Infinity, opts = {}) {
  const { motivos = {}, rejeitando = null, erroMotivo = "", selecionados = {} } = opts;
  const lidos = byPriority(items || []).slice(0, feitos);
  const pendentes = lidos.filter((it) => it.destino !== "automatico");
  if (pendentes.length === 0) {
    return `<p class="vazio">Nenhum caso aguardando pessoa.</p>`;
  }
  const loteveis = pendentes.filter((it) => it.destino === "aprovacao" && !(decisions || {})[it.alias]);
  const nSel = loteveis.filter((it) => selecionados[it.alias]).length;
  const lote = loteveis.length
    ? `<div class="lote">
  <label class="check"><input type="checkbox" data-selecionar-todos ${nSel === loteveis.length ? "checked" : ""}> Selecionar os ${loteveis.length} de aprovação</label>
  <button type="button" class="btn btn-primario" data-aprovar-lote ${nSel ? "" : "disabled"}>Aprovar selecionados (${nSel})</button>
</div>`
    : "";
  const rows = pendentes
    .map((it) => {
      const d = decisions && decisions[it.alias];
      const motivoRej = d === "rejeitar" && motivos[it.alias] ? ` Motivo: ${motivos[it.alias]}.` : "";
      const status = d
        ? `<p class="consequencia"><strong>${e(DECISOES[d] ?? d)}.</strong>${e(motivoRej)} ${e(consequencia(it, d))}<button type="button" class="link" data-desfazer="${e(it.alias)}">Desfazer</button></p>
  <p class="registrada">Simulação: a decisão fica só neste navegador.</p>`
        : "";
      const botoes = (ACOES_HUMANAS[it.destino] || [])
        .map(
          ([valor, rotulo, cls]) =>
            `<button type="button" class="btn ${cls}" data-decisao="${valor}" data-alias="${e(it.alias)}" aria-pressed="${d === valor}">${rotulo}</button>`
        )
        .join("\n    ");
      // Rejeitar exige motivo: o clique abre o campo; a decisão só vale ao confirmar.
      const campoMotivo = rejeitando === it.alias
        ? `<div class="motivo-rejeicao">
  <label class="rotulo-edicao" for="motivo-${e(it.alias)}">Motivo da rejeição (obrigatório)</label>
  <input id="motivo-${e(it.alias)}" class="campo" type="text" maxlength="200" data-motivo="${e(it.alias)}" placeholder="Ex.: falta a foto do produto">
  ${erroMotivo ? `<p class="erro-edicao" role="alert">${e(erroMotivo)}</p>` : ""}
  <div class="aprov-botoes">
    <button type="button" class="btn btn-primario" data-confirmar-rejeicao="${e(it.alias)}">Confirmar rejeição</button>
    <button type="button" class="btn btn-secundario" data-cancelar-rejeicao="${e(it.alias)}">Cancelar</button>
  </div>
</div>`
        : "";
      const editada = edits && edits[it.alias] != null;
      const texto = editada ? edits[it.alias] : it.resposta_cliente;
      const resposta = texto
        ? `<p class="rotulo-resposta">Resposta que vai ao cliente${editada ? " (editada pela atendente)" : ""}</p><blockquote class="resposta resposta-curta">${e(texto)}</blockquote>`
        : `<p class="nota">Nada é enviado ao cliente até a decisão.</p>`;
      const check = it.destino === "aprovacao" && !d
        ? `<input type="checkbox" class="sel" aria-label="Selecionar ${e(it.alias)}" data-selecionar="${e(it.alias)}" ${selecionados[it.alias] ? "checked" : ""}>`
        : "";
      return `<li class="aprov">
  <div class="aprov-info">
    ${check}
    <span class="prio" title="Prioridade">${e(it.prioridade)}</span>
    <button type="button" class="link" data-alias="${e(it.alias)}">${e(it.alias)}</button>
    <span class="categoria-cab">${e(rotuloCategoria(it.categoria))}</span>
    ${destinoBadge(it.destino)}
  </div>
  <p class="motivo">${e(it.motivo)}</p>
  ${resposta}
  ${d ? "" : `<div class="aprov-botoes">
    ${botoes}
  </div>`}
  ${campoMotivo}
  ${status}
</li>`;
    })
    .join("\n");
  return `${lote}<ol class="aprovacoes">${rows}</ol><p class="nota">Simulação: as decisões ficam só neste navegador; nada é enviado a nenhum sistema.</p>`;
}

// Prazo de primeira resposta (pipeline/fatos.sla): {texto, nivel} ou null quando já respondida.
export function prazoResposta(item) {
  const v = ((item.dados || []).find((d) => d.rotulo === "SLA de primeira resposta") || {}).valor;
  if (!v || v === "já respondida") return null;
  const venc = /vencido há (\d+)/.exec(v);
  if (venc) return { texto: "prazo vencido", nivel: "vencido", min: -Number(venc[1]) };
  const m = /(\d+) min restantes/.exec(v);
  if (!m) return null;
  const min = Number(m[1]);
  const texto = min < 60 ? `vence em ${min} min` : `vence em ${Math.round(min / 60)} h`;
  return { texto, nivel: min <= 240 ? "atencao" : "normal", min };
}

// Filtro da fila: destino ("" = todos), canal ("" = todos) e busca por código ou assunto.
export function passaFiltro(it, f = {}) {
  if (f.destino && it.destino !== f.destino) return false;
  if (f.canal && it.canal !== f.canal) return false;
  const q = (f.busca || "").trim().toLowerCase();
  if (q && !`${it.alias} ${rotuloCategoria(it.categoria)}`.toLowerCase().includes(q)) return false;
  return true;
}

export function filtroAtivo(f = {}) {
  return Boolean(f.destino || f.canal || (f.busca || "").trim());
}

export function renderLog(item) {
  if (!item) {
    return `<p class="vazio">Selecione uma conversa na fila para ver o log.</p>`;
  }
  if (!item.log || item.log.length === 0) {
    return `<p class="vazio">Sem registros de log para ${e(item.alias)}.</p>`;
  }
  const total = item.log.reduce((acc, r) => acc + (Number(r.ms) || 0), 0);
  // Com classificações salvas (sem chamada ao modelo) o tempo de "classificar" fica ~0.
  const semTempo = item.log.some((r) => r.etapa === "classificar" && (Number(r.ms) || 0) < 1);
  const nota = semTempo
    ? `<p class="nota-log">Tempos da etapa de classificação não são medidos neste modo (respostas salvas).</p>`
    : "";
  const rows = item.log
    .map((r) => `<tr><td>${e(r.etapa)}</td><td>${e(r.resultado)}</td><td class="num">${e(r.ms)}</td></tr>`)
    .join("");
  return `<div class="tabela-wrap"><table class="log">
  <thead><tr><th>Etapa</th><th>Resultado</th><th class="num">ms</th></tr></thead>
  <tbody>${rows}</tbody>
  <tfoot><tr><td colspan="2">Total</td><td class="num">${e(total)}</td></tr></tfoot>
</table></div>${nota}`;
}

// ---- Encaminhar com nota interna (simulado no navegador) ----
// Áreas aceitas por acionar_pessoa (pipeline/tools.py AREAS).
export const AREAS = {
  supervisao: "Supervisão", logistica: "Logística", qualidade: "Qualidade",
  producao: "Produção", juridico: "Jurídico", comercial: "Comercial",
};

export function renderEncaminhar(item, enc = null, erro = "") {
  if (!item || item.destino === "automatico") return "";
  if (enc) {
    return `<section class="encaminhar">
  <h4>Encaminhamento interno</h4>
  <p class="consequencia"><strong>Encaminhado para ${e(AREAS[enc.area] ?? enc.area)}.</strong> Nota: ${e(enc.nota)} <button type="button" class="link" data-desfazer-enc="${e(item.alias)}">Desfazer</button></p>
  <p class="registrada">Simulação: o encaminhamento fica só neste navegador; o cliente não vê a nota.</p>
</section>`;
  }
  const opcoes = Object.entries(AREAS).map(([v, r]) => `<option value="${v}">${e(r)}</option>`).join("");
  return `<section class="encaminhar">
  <h4>Encaminhar para outra área</h4>
  <div class="enc-linha">
    <select class="campo" data-enc-area="${e(item.alias)}" aria-label="Área de destino">${opcoes}</select>
    <input class="campo" type="text" maxlength="200" data-enc-nota="${e(item.alias)}" placeholder="Nota interna (o cliente não vê)" aria-label="Nota interna">
    <button type="button" class="btn btn-secundario" data-encaminhar="${e(item.alias)}">Encaminhar</button>
  </div>
  ${erro ? `<p class="erro-edicao" role="alert">${e(erro)}</p>` : ""}
</section>`;
}

// ---- Respostas prontas: trechos neutros, sem promessa de prazo, valor ou reembolso. ----
export const RESPOSTAS_PRONTAS = [
  ["saudacao", "Saudação", "Olá! Obrigado por falar com a gente."],
  ["desculpas", "Pedido de desculpas", "Sentimos muito pelo transtorno."],
  ["foto", "Pedir foto", "Pode nos enviar uma foto do produto e da embalagem? Assim conseguimos analisar o seu caso."],
  ["numero", "Pedir nº do pedido", "Pode nos informar o número do pedido?"],
  ["acompanhando", "Acompanhamento", "Seguimos acompanhando o seu caso e retornamos por aqui."],
  ["encerramento", "Encerramento", "Qualquer dúvida, estamos à disposição."],
];

export function renderProntas(alias) {
  const opcoes = RESPOSTAS_PRONTAS.map(([k, r]) => `<option value="${k}">${e(r)}</option>`).join("");
  return `<div class="prontas">
  <select class="campo" data-pronta-sel="${e(alias)}" aria-label="Resposta pronta"><option value="">Respostas prontas…</option>${opcoes}</select>
  <button type="button" class="btn btn-secundario" data-inserir-pronta="${e(alias)}">Inserir no texto</button>
</div>`;
}

export function textoPronto(chave) {
  return (RESPOSTAS_PRONTAS.find(([k]) => k === chave) || [])[2] || "";
}

// ---- Painel de impacto: números calculados do próprio export. ----
export function calcularImpacto(items, decisions = {}, encs = {}, resolvidos = {}) {
  const total = items.length;
  const s = summarize(items);
  const porCat = {};
  const porCanal = {};
  let urgentes = 0;
  for (const it of items) {
    porCat[it.categoria] = (porCat[it.categoria] || 0) + 1;
    porCanal[it.canal] = (porCanal[it.canal] || 0) + 1;
    const p = prazoResposta(it);
    if (it.destino !== "automatico" && p && p.nivel !== "normal") urgentes += 1;
  }
  const humanos = items.filter((it) => it.destino !== "automatico");
  const decididos = humanos.filter((it) => decisions[it.alias] || encs[it.alias]).length;
  return {
    total, automaticas: s.automaticas,
    pctAuto: total ? Math.round((s.automaticas / total) * 100) : 0,
    humanos: humanos.length, decididos, urgentes,
    resolvidos: humanos.filter((it) => resolvidos[it.alias]).length,
    porCat: Object.entries(porCat).sort((a, b) => b[1] - a[1]),
    porCanal: Object.entries(porCanal).sort((a, b) => b[1] - a[1]),
  };
}

function barras(pares, total, rotulo) {
  return `<ul class="barras">${pares.map(([k, n]) => `<li><span class="barra-rot">${e(rotulo(k))}</span><span class="barra-trilho"><span style="width:${total ? Math.round((n / total) * 100) : 0}%"></span></span><span class="barra-num">${n}</span></li>`).join("")}</ul>`;
}

export function renderImpacto(items, decisions = {}, encs = {}, feitos = Infinity, resolvidos = {}, ref = null) {
  if (feitos < items.length) {
    return `<p class="vazio">O painel aparece quando o agente terminar a fila (${Math.min(feitos, items.length)} de ${items.length} lidas). Aperte ▶ Iniciar o agente na Fila de entrada.</p>`;
  }
  const m = calcularImpacto(items, decisions, encs, resolvidos);
  const t = tempoPoupado(items, ref);
  const destaque = [
    [`${m.pctAuto}%`, "resolvido pelo agente", `${m.automaticas} de ${m.total} conversas`],
    [m.humanos, "precisam de pessoa", "aprovação, atendente ou supervisor"],
    [m.urgentes, "com prazo apertado", "casos humanos com SLA de até 4 h ou vencido"],
    [`${m.resolvidos}/${m.humanos}`, "resolvidos pela atendente", "casos humanos marcados como resolvidos"],
    ...(t ? [[`≈ ${t.texto}`, "de trabalho poupado", `${t.n} conversas × ${String(ref.media_minutos).replace(".", ",")} min (média de ${ref.conversas} atendimentos)`]] : []),
  ].map(([n, l, a]) => `<div class="card"><span class="card-num">${e(n)}</span><span class="card-label">${e(l)}</span><span class="card-ajuda">${e(a)}</span></div>`).join("");
  return `<div class="cards">${destaque}</div>
<div class="impacto-grade">
  <section><h4>Por assunto</h4>${barras(m.porCat, m.total, rotuloCategoria)}</section>
  <section><h4>Por canal</h4>${barras(m.porCanal, m.total, (c) => CANAIS[c] ?? c)}</section>
</div>
<div class="aprov-botoes"><button type="button" class="btn btn-primario" data-baixar-csv>Baixar CSV da fila</button></div>
<p class="nota">Números calculados do export público (conversas simuladas). Tempo poupado é estimativa: usa a média histórica de minutos trabalhados por conversa em tempo_por_conversa.csv. O CSV leva as decisões, edições e encaminhamentos feitos neste navegador.</p>`;
}

// ---- CSV: separador ";" (Excel em português), sempre entre aspas e protegido contra fórmula. ----
function celula(v) {
  let s = String(v ?? "");
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return `"${s.replace(/"/g, '""')}"`;
}

export function paraCsv(items, { decisions = {}, edits = {}, motivos = {}, encs = {}, resolvidos = {} } = {}) {
  const cab = ["codigo", "prioridade", "canal", "marca", "assunto", "destino", "acao", "motivo",
    "prazo", "decisao_humana", "motivo_rejeicao", "encaminhado_para", "nota_interna", "resolvido", "resposta_cliente", "resposta_editada"];
  const linhas = byPriority(items).map((it) => {
    const enc = encs[it.alias];
    return [it.alias, it.prioridade, CANAIS[it.canal] ?? it.canal, it.marca_grupo, rotuloCategoria(it.categoria),
      DESTINOS[it.destino] ?? it.destino, it.acao, it.motivo, prazoResposta(it)?.texto ?? "",
      DECISOES[decisions[it.alias]] ?? "", motivos[it.alias] ?? "", enc ? AREAS[enc.area] ?? enc.area : "",
      enc?.nota ?? "", resolvidos[it.alias] ? "sim" : "não", edits[it.alias] ?? it.resposta_cliente ?? "", edits[it.alias] != null ? "sim" : "não"];
  });
  return [cab, ...linhas].map((l) => l.map(celula).join(";")).join("\r\n");
}

// ---- Marcar como resolvido (caso humano; simulado no navegador) ----
export function renderResolvido(item, resolvido = false) {
  if (!item || item.destino === "automatico") return "";
  return resolvido
    ? `<section class="resolvido"><p class="consequencia"><strong>✓ Caso resolvido pela atendente.</strong> <button type="button" class="link" data-reabrir="${e(item.alias)}">Reabrir</button></p></section>`
    : `<section class="resolvido"><button type="button" class="btn btn-primario" data-resolver="${e(item.alias)}">✓ Marcar como resolvido</button></section>`;
}

// Tempo poupado: conversas resolvidas pelo agente × média histórica de minutos trabalhados.
export function tempoPoupado(items, ref) {
  if (!ref || !(ref.media_minutos > 0)) return null;
  const n = items.filter((it) => it.destino === "automatico").length;
  const min = Math.round(n * ref.media_minutos);
  const h = Math.floor(min / 60);
  return { n, min, texto: h ? `${h} h ${String(min % 60).padStart(2, "0")} min` : `${min} min` };
}
