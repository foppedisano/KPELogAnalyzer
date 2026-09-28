"use strict";
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const number = (n) =>
  new Intl.NumberFormat("it-IT", { maximumFractionDigits: 2 }).format(n ?? 0);
const shortIdentity = (s) => (s || "Identità non disponibile").split("@")[0];
const stamp = (s) => (s ? s.slice(0, 19) : "—");
const timeValue = (s) => Date.parse(s.replace(" ", "T") + "Z"); // neutral clock axis, no assumed timezone
const duration = (c) =>
  c.connected && c.end
    ? number(Math.max(0, (timeValue(c.end) - timeValue(c.connected)) / 1000)) +
      " s"
    : "—";
let state = {
  calls: [],
  perspectives: [],
  metrics: [],
  selected: new Set(),
  view: "calls",
  current: null,
};
let chartCleanup = null,
  uploadFiles = [],
  renderToken = 0;
async function api(path, options = {}) {
  const r = await fetch("/api/" + path, options);
  const data = await r.json();
  if (!r.ok) throw Error(data.error || "Errore del servizio");
  return data;
}
function post(path, obj, method = "POST") {
  return api(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(obj),
  });
}
function notice(text, error = false) {
  const n = $("#notice");
  n.textContent = text;
  n.className = error ? "error" : "";
  n.hidden = false;
}
function safe(fn) {
  return (...args) => {
    try {
      return Promise.resolve(fn(...args)).catch((e) => notice(e.message, true));
    } catch (e) {
      notice(e.message, true);
    }
  };
}
function title(eyebrow, heading, sub, extra = "") {
  return `<div class="page-title"><div><div class="eyebrow">${eyebrow}</div><h1>${heading}</h1><p class="subtitle">${sub}</p></div>${extra}</div>`;
}
function empty(heading, text) {
  return `<div class="empty"><div class="empty-icon">⌁</div><h2>${heading}</h2><p>${text}</p></div>`;
}
function updateSelection() {
  $("#selection-count").textContent = state.selected.size;
  $$(".call-check").forEach((c) => (c.checked = state.selected.has(+c.value)));
}
async function refresh() {
  const [calls, perspectives, metrics, overview] = await Promise.all([
    api("calls"),
    api("perspectives"),
    api("metric-names"),
    api("overview"),
  ]);
  Object.assign(state, { calls, perspectives, metrics, overview });
  $("#nav-count").textContent = calls.length;
}
function setView(view) {
  window.scrollTo(0, 0);
  state.view = view;
  state.current = null;
  $$("nav button").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === view),
  );
  $("#breadcrumb").textContent = $(`nav [data-view="${view}"]`)
    .textContent.replace(/\d+$/, "")
    .trim();
  return render();
}
async function render() {
  const token = ++renderToken;
  if (chartCleanup) {
    chartCleanup();
    chartCleanup = null;
  }
  const page = $("#page");
  const views = {
    calls: renderCalls,
    mos: renderMos,
    geography: renderGeography,
    compare: renderCompare,
    sources: renderSources,
    logs: renderLogs,
    sql: renderSQL,
    analytics: renderAnalytics,
    conversations: renderConversations,
    diagnostics: renderDiagnostics,
    catalog: renderCatalog,
    manual: renderManual,
    identities: renderIdentities,
    topology: renderTopology,
  };
  await views[state.view](page, token);
}
function stats() {
  const o = state.overview;
  return `<div class="stats"><div class="stat"><span>Chiamate ricostruite</span><strong>${number(o.calls)}</strong><small>Identità SIP e sessioni locali</small></div><div class="stat"><span>Archivi importati</span><strong>${number(o.imports)}</strong><small>Export conservati</small></div><div class="stat"><span>Campioni metrici</span><strong>${number(o.metrics)}</strong><small>${number(o.unassigned_metrics)} non attribuiti</small></div><div class="stat"><span>Eventi indicizzati</span><strong>${number(o.events)}</strong><small>Con file e riga di origine</small></div></div>`;
}
function mosCell(c, direction) {
  const summary = c.mos || {}, m = summary[direction];
  const source = `Sorgente: ${summary.source || 'non disponibile'} · prospettiva #${summary.perspective_id || '—'}. `;
  if (!m) return `<td class="mos-cell muted" title="${esc(source + (summary[direction+'_reason'] || summary.reason || 'Dati non disponibili'))}">—</td>`;
  const color = v => v < 3 ? 'mos-low' : v < 4 ? 'mos-mid' : 'mos-good';
  const coverage = m.coverage_percent == null ? 'durata totale non nota' : `${number(m.coverage_percent)}% della finestra osservata`;
  const tip = source + `${m.basis === 'local' ? 'Ricezione locale' : 'Report remoto RTCP'}; ${summary.role_basis === 'app_assumed' ? 'app presunta' : 'app confermata'}. Media pesata su ${number(m.covered_seconds)} s; ${coverage}. Minimo: evento #${m.minimum_event_id}; massimo: evento #${m.maximum_event_id}.`;
  return `<td class="mos-cell" title="${esc(tip)}"><strong class="${color(m.mean)}">${number(m.mean)}</strong> <small>media</small><div><span class="${color(m.minimum)}">${number(m.minimum)}</span> <small>min</small> · <span class="${color(m.maximum)}">${number(m.maximum)}</span> <small>max</small></div><small>cop. ${m.coverage_percent == null ? '—' : number(m.coverage_percent)+'%'}</small></td>`;
}
function callSortValue(c, key) {
  if (key.startsWith('mos.')) { const [, direction, stat] = key.split('.'); return c.mos?.[direction]?.[stat] ?? null; }
  if (key === 'duration') return c.connected && c.end ? Math.max(0, timeValue(c.end)-timeValue(c.connected)) : null;
  return c[key] ?? null;
}
function callTable(calls) {
  return `<div class="table-wrap"><table><thead><tr><th aria-label="Seleziona"></th><th>Chiamata / interlocutori</th><th>MOS ↓ downstream</th><th>MOS ↑ upstream</th><th>Stato osservato</th><th>Durata connessa</th><th>Prospettive</th><th>Metriche</th></tr></thead><tbody>${calls.map((c) => `<tr class="call-row" data-id="${c.id}" tabindex="0"><td><input type="checkbox" class="call-check" aria-label="Seleziona chiamata ${c.id}" value="${c.id}" ${state.selected.has(c.id) ? "checked" : ""}></td><td><div class="identity" title="${esc(c.caller + " → " + c.callee)}">${esc(shortIdentity(c.caller))} <span class="muted">→</span> ${esc(shortIdentity(c.callee))}</div><div class="call-date">${stamp(c.start)} <span class="muted">· #${c.id}</span></div></td>${mosCell(c,"downstream")}${mosCell(c,"upstream")}<td><span class="tag ${c.status.includes("failed") ? "warn" : c.status.includes("partial") ? "neutral" : ""}">${esc(c.status)}</span></td><td class="mono nowrap">${duration(c)}</td><td>${c.perspectives} <span class="muted">sorgenti</span></td><td class="mono">${number(c.metrics)}</td></tr>`).join("")}</tbody></table></div>`;
}
function bindCalls() {
  $$(".call-row").forEach((row) => {
    row.onclick = safe((e) => {
      if (e.target.matches("input")) return;
      return detail(+row.dataset.id);
    });
    row.onkeydown = safe((e) => {
      if (e.target === row && e.key === "Enter") return detail(+row.dataset.id);
    });
  });
  $$(".call-check").forEach(
    (input) =>
      (input.onchange = () => {
        input.checked
          ? state.selected.add(+input.value)
          : state.selected.delete(+input.value);
        updateSelection();
        if (state.view === "compare" && state.current === null) safe(render)();
      }),
  );
}
function renderCalls(page) {
  page.innerHTML =
    title(
      "ANALISI DEL TRAFFICO VOCE",
      "Ogni chiamata, una storia.",
      "Ricostruisci le sessioni, confronta i punti di vista e risali all’evidenza nei log.",
      `<span class="tag">● Workspace privato</span>`,
    ) +
    stats() +
    `<div class="panel"><div class="panel-head"><h2>Registro chiamate</h2><div class="toolbar"><input id="call-search" aria-label="Cerca chiamate" placeholder="Cerca interlocutore o Call-ID…"><button id="compare-selected">Confronta selezionate →</button></div></div><div class="call-sort toolbar"><label>Ordina per <select id="call-sort"><option value="start">Data</option><option value="duration">Durata connessa</option><option value="status">Stato osservato</option><option value="metrics">Numero metriche</option>${['downstream','upstream'].map(d=>['minimum','mean','maximum'].map((v,i)=>`<option value="mos.${d}.${v}">MOS ${d} · ${['minimo','medio','massimo'][i]}</option>`).join('')).join('')}</select></label><label>Ordine <select id="call-order"><option value="asc">Crescente</option><option value="desc">Decrescente</option></select></label><span class="muted">MOS: media pesata in evidenza · minimo e massimo · copertura temporale</span></div><div id="call-list"></div><div class="table-note">Orari originali dei log, senza fuso dichiarato. Seleziona più righe per confrontare chiamate o partecipanti. Massimo 2.000 chiamate elencate; ordinamento su queste righe. MOS a profilo fisso, sola perdita RTCP: rosso &lt;3, arancio 3–4, verde ≥4 (soglie indicative). Prospettiva dell’ultimo import non duplicato, senza unire flussi; sorgente nel tooltip. Dati mancanti in fondo.</div></div>`;
  function list() {
    const text = $("#call-search").value.toLowerCase();
    const calls = state.calls.filter((c) =>
      (c.caller + c.callee + c.sip_call_id).toLowerCase().includes(text),
    );
    const key = $("#call-sort").value, sign = $("#call-order").value === 'asc' ? 1 : -1;
    calls.sort((a,b) => {
      const x = callSortValue(a,key), y = callSortValue(b,key);
      if (x == null || y == null) return x == null && y == null ? a.id-b.id : x == null ? 1 : -1;
      return sign * (typeof x === 'string' ? x.localeCompare(y) : x-y) || a.id-b.id;
    });
    state.callSort = key; state.callOrder = $("#call-order").value;
    $("#call-list").innerHTML = calls.length
      ? callTable(calls)
      : empty(
          "Nessuna chiamata da mostrare",
          state.calls.length
            ? "Modifica i criteri di ricerca."
            : "Importa il primo ZIP per iniziare l’analisi.",
        );
    bindCalls();
  }
  $("#call-sort").value = state.callSort || 'start';
  $("#call-order").value = state.callOrder || 'desc';
  $("#call-sort").onchange = () => { $("#call-order").value = $("#call-sort").value.startsWith('mos.') ? 'asc' : 'desc'; list(); };
  $("#call-order").onchange = list;
  list();
  $("#call-search").oninput = list;
  $("#compare-selected").onclick = safe(() => setView("compare"));
}
async function detail(id) {
  window.scrollTo(0, 0);
  state.current = id;
  if (chartCleanup) {
    chartCleanup();
    chartCleanup = null;
  }
  ++renderToken;
  const c = state.calls.find((c) => c.id === id);
  const ps = state.perspectives.filter((p) => p.call_id === id);
  $("#breadcrumb").textContent = "Chiamata #" + id;
  $("#page").innerHTML =
    `<button class="back" id="back-calls">← Registro chiamate</button>` +
    title(
      "DETTAGLIO CHIAMATA",
      `${esc(shortIdentity(c.caller))} <span class="muted">→</span> ${esc(shortIdentity(c.callee))}`,
      "Segnalazione, statistiche e contesto della sessione.",
      `<button id="select-detail">${state.selected.has(id) ? "Rimuovi dal confronto" : "Aggiungi al confronto"}</button>`,
    ) +
    `<div id="chart-panel"></div><div class="detail-meta"><div><span>PRIMA EVIDENZA</span><strong>${stamp(c.start)}</strong></div><div><span>CONNESSIONE</span><strong>${stamp(c.connected)}</strong></div><div><span>ULTIMA TERMINAZIONE</span><strong>${stamp(c.end)}</strong></div><div><span>DURATA CONNESSA*</span><strong>${duration(c)}</strong></div></div><p class="mono muted">Call-ID: ${esc(c.sip_call_id || "Non disponibile · sessione locale")}</p><p class="muted">* Intervallo osservato; con più sorgenti non corregge eventuali differenze tra gli orologi.</p><div class="panel"><div class="panel-head"><h2>Punti di vista</h2><span class="tag neutral">${ps.length} prospettive archiviate</span></div>${ps.map((p) => `<div class="perspective"><strong>${esc(p.label)} <span class="tag neutral">${esc(p.direction)}</span> <span class="tag">${esc(p.status)}</span></strong><small>${esc(sourceDescription(p))}</small>${p.duplicate_of ? `<small class="muted">Copia storica di P${p.duplicate_of}: esclusa dal grafico normale.</small>` : ""}<small>App ${esc(p.app_version || "versione non documentata")} ${p.version_event_id ? "(evento " + p.version_event_id + ")" : ""} · Linea ${p.line_id ?? "non nota"} · ${esc(p.evidence)} · offset grafico ${p.clock_offset}s</small><small>${stamp(p.start)} → ${stamp(p.end)}</small></div>`).join("")}</div><button id="open-mos">MOS e ricezione di questa chiamata →</button><div id="analysis-panel"></div><div id="detail-events"></div>`;
  $("#back-calls").onclick = safe(() => setView("calls"));
  $("#select-detail").onclick = () => {
    state.selected.has(id) ? state.selected.delete(id) : state.selected.add(id);
    updateSelection();
    $("#select-detail").textContent = state.selected.has(id)
      ? "Rimuovi dal confronto"
      : "Aggiungi al confronto";
  };
  $("#open-mos").onclick = safe(() => { window.mosLocal = ps[0]?.id; return setView("mos"); });
  await mountChart($("#chart-panel"), [id], "derived.mos_reference|incoming");
  await mountAnalysis($("#analysis-panel"), id);
  await mountEvents($("#detail-events"), { call: id }, true);
}
async function renderCompare(page) {
  const ids = [...state.selected];
  page.innerHTML = title(
    "CONFRONTO MULTISORGENTE",
    "Metti a confronto le evidenze.",
    "Sovrapponi metriche di chiamate e partecipanti. Ogni colore mantiene distinta sorgente, direzione, flusso e SSRC.",
  );
  if (!ids.length) {
    page.innerHTML += empty(
      "Seleziona le chiamate da confrontare",
      "Apri il registro chiamate e seleziona le righe che ti interessano.",
    );
    return;
  }
  page.innerHTML += `<div class="panel"><div class="panel-head"><h2>${ids.length} chiamate selezionate</h2><button id="clear-selection">Svuota selezione</button></div>${callTable(state.calls.filter((c) => state.selected.has(c.id)))}</div><div id="chart-panel"></div><div class="inline-note">L’allineamento relativo parte dalla prima evidenza di ciascun punto di vista. Per confrontare lo stesso istante usa l’asse assoluto e correggi gli orologi nella sezione Sorgenti.</div><button id="group-selection">Collega come conversazione / conferenza</button>`;
  bindCalls();
  $("#clear-selection").onclick = safe(() => {
    state.selected.clear();
    updateSelection();
    return render();
  });
  $("#group-selection").onclick = safe(() => setView("conversations"));
  await mountChart($("#chart-panel"), ids);
}
const colors = [
  "#008d86",
  "#d28b40",
  "#5e77ce",
  "#b46184",
  "#55a56b",
  "#a37dc1",
  "#dd6b52",
  "#397e9c",
];
async function mountChart(root, ids, initialMetric = "rtcp.rtt") {
  if (root) await mountMultiChart(root, ids, initialMetric);
}
async function mountEvents(root, base = {}, compact = false) {
  if (!root) return;
  root.innerHTML = `<div class="panel"><div class="panel-head"><h2>${compact ? "Eventi della chiamata" : "Ricerca negli eventi"}</h2><div class="toolbar"><input class="event-search" placeholder="Cerca testo, errore, Call-ID…" aria-label="Cerca nei log"><select class="event-level" aria-label="Livello"><option value="">Tutti i livelli</option><option>ERROR</option><option>WARNING</option><option>INFO</option><option>DEBUG</option></select><button class="event-run">Cerca</button></div></div><div class="event-list"></div><div class="pager"><button class="event-prev small-button">← Precedenti</button><span class="event-range"></span><button class="event-next small-button">Successivi →</button></div></div>`;
  let offset = 0,
    ticket = 0;
  async function load() {
    const t = ++ticket;
    const params = new URLSearchParams({
      ...base,
      search: $(".event-search", root).value,
      level: $(".event-level", root).value,
      offset,
    });
    const data = await api("events?" + params);
    if (t !== ticket || !root.isConnected) return;
    $(".event-list", root).innerHTML = data.events.length
      ? data.events
          .map(
            (e) =>
              `<details class="event"><summary><time>${stamp(e.ts)}</time><span class="tag ${/ERROR|WARN/.test(e.level) ? "warn" : "neutral"}">${esc(e.level || e.kind)}</span><span class="event-title">${esc(e.text.split("\n")[0])}</span></summary><div class="source">${esc(e.filename)}:${e.line_no} · evento #${e.id} · ${e.call_id ? "chiamata #" + e.call_id : "non attribuito"}</div><pre>${esc(e.text)}</pre></details>`,
          )
          .join("")
      : empty("Nessun evento", "Prova una ricerca diversa.");
    $(".event-range", root).textContent =
      `${offset + (data.events.length ? 1 : 0)}–${offset + data.events.length}`;
    $(".event-prev", root).disabled = offset === 0;
    $(".event-next", root).disabled = !data.more;
  }
  $(".event-run", root).onclick = safe(() => {
    offset = 0;
    return load();
  });
  $(".event-search", root).onkeydown = safe((e) => {
    if (e.key === "Enter") {
      offset = 0;
      return load();
    }
  });
  $(".event-level", root).onchange = safe(() => {
    offset = 0;
    return load();
  });
  $(".event-prev", root).onclick = safe(() => {
    offset = Math.max(0, offset - 100);
    return load();
  });
  $(".event-next", root).onclick = safe(() => {
    offset += 100;
    return load();
  });
  await load();
}
async function renderLogs(page, token) {
  const files = await api("files");
  if (token !== renderToken) return;
  page.innerHTML =
    title(
      "EVIDENZE ORIGINALI",
      "Dentro i log.",
      "Cerca in tutti i file, inclusi gli eventi non attribuiti a una chiamata. Le righe si riferiscono al testo con newline normalizzati.",
    ) +
    `<div class="toolbar"><label>File sorgente<select id="log-file"><option value="">Tutti i file</option>${files.map((f) => `<option value="${f.id}">${esc(f.label + " / " + f.name)}</option>`).join("")}</select></label><label><input id="unassigned" type="checkbox"> Solo non attribuiti</label></div><div id="log-events"></div>`;
  const load = () =>
    mountEvents($("#log-events"), {
      file: $("#log-file").value,
      unassigned: $("#unassigned").checked ? "1" : "0",
    });
  $("#log-file").onchange = safe(load);
  $("#unassigned").onchange = safe(load);
  await load();
}
async function renderSources(page, token) {
  const [imports, files] = await Promise.all([api("imports"), api("files")]);
  if (token !== renderToken) return;
  page.innerHTML =
    title(
      "PROVENIENZA E QUALITÀ",
      "Ogni sorgente ha un punto di vista.",
      "Le chiamate conservate sono contate una volta per ZIP; gli scarti della stessa sorgente sono indicati a parte. Nuove/già presenti segue l’ordine di importazione. La correzione orologio si applica solo al grafico assoluto; i timestamp originali rimangono disponibili.",
    ) +
    `<div class="panel">${
      imports.length
        ? imports
            .map(
              (i) =>
                `<div class="source-card"><form class="source-edit" data-id="${i.id}"><label>Nome dispositivo / sorgente<input name="label" value="${esc(i.label)}" maxlength="120" required></label><label>Correzione orologio (s)<input name="offset" type="number" min="-86400" max="86400" step="0.001" value="${i.clock_offset}"></label><button>Salva</button></form><p>${esc(sourceDescription(i))}</p><p class="mono muted">${esc(i.name)} · ${i.file_count} file · ${number(i.event_count)} eventi · <strong>${number(i.call_count)} chiamate distinte</strong></p><p>${number(i.new_call_count)} nuove nel DB · ${number(i.existing_call_count)} già presenti nelle importazioni precedenti</p><p>Identità sorgente: <strong>${esc(i.producer?.producer_key || "non determinata")}</strong> · ${esc(i.producer?.basis || "")}</p><p><strong>${number(i.producer?.skipped_calls || 0)} chiamate ignorate</strong> perché già importate dalla stessa sorgente · ${number(i.producer?.historical_duplicates || 0)} copie storiche riconosciute</p><details><summary>Avvisi di importazione (${JSON.parse(i.warnings).length})</summary><ul>${JSON.parse(
                  i.warnings,
                )
                  .map((w) => `<li>${esc(w)}</li>`)
                  .join("")}</ul></details></div>`,
            )
            .join("")
        : empty(
            "Nessuna sorgente",
            "Importa uno ZIP per vedere la copertura dei file.",
          )
    }</div><div class="panel"><div class="panel-head"><h2>Copertura dei file</h2><span class="muted">Il parser “raw” conserva il testo ricercabile</span></div><div class="table-wrap"><table><thead><tr><th>File / sorgente</th><th>Parser</th><th>Primo evento</th><th>Ultimo evento</th><th>Record</th></tr></thead><tbody>${files.map((f) => `<tr><td>${esc(f.name)}<div class="call-date">${esc(f.label)}</div></td><td><span class="tag neutral">${esc(f.parser)}</span></td><td class="mono nowrap">${stamp(f.first_ts)}</td><td class="mono nowrap">${stamp(f.last_ts)}</td><td>${number(f.records)}</td></tr>`).join("")}</tbody></table></div></div>`;
  $$(".source-edit").forEach(
    (form) =>
      (form.onsubmit = safe(async (e) => {
        e.preventDefault();
        await post(
          "imports",
          {
            id: +form.dataset.id,
            label: form.elements.label.value,
            clock_offset: +form.elements.offset.value,
          },
          "PATCH",
        );
        await refresh();
        notice("Etichetta e correzione orologio salvate.");
      })),
  );
}
const presets = {
  "Qualità RTCP per chiamata":
    "SELECT call_id, name, direction, unit, COUNT(*) AS samples, ROUND(AVG(value), 3) AS mean, MAX(value) AS peak\nFROM metrics\nWHERE name LIKE 'rtcp.%' AND valid = 1\nGROUP BY call_id, name, direction, unit\nORDER BY call_id DESC;",
  "Valori anomali":
    "SELECT m.call_id, m.ts, m.name, m.value, m.unit, f.name AS file, e.line_no\nFROM metrics m JOIN events e ON e.id=m.event_id JOIN files f ON f.id=e.file_id\nWHERE m.valid=0 ORDER BY m.ts DESC LIMIT 100;",
  "Evidenze conferenza":
    "SELECT call_id, ts, text FROM events\nWHERE text LIKE '%conference%'\nAND text NOT LIKE '%not present%'\nAND text NOT LIKE '%Retrieving%'\nORDER BY ts DESC LIMIT 100;",
  "Schema database":
    "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;",
};
async function mountAnalysis(root, id) {
  if (!root) return;
  const a = await api("analysis?call=" + id);
  if (!root.isConnected) return;
  root.innerHTML = `<div class="panel"><div class="panel-head"><h2>Riepilogo delle evidenze</h2><span class="tag ${a.error_events ? "warn" : "neutral"}">${a.error_events} eventi ERROR/FATAL · ${a.invalid_metrics} valori anomali</span></div><div class="panel-body"><p class="muted">Statistiche descrittive sui campioni RTCP validi, aggregate per sorgente e direzione. Un picco o un errore nel log è un’indicazione da approfondire, non una diagnosi della causa.</p>${a.summary.length ? `<div class="table-wrap"><table><thead><tr><th>Sorgente</th><th>Parametro</th><th>Direzione</th><th>Campioni</th><th>Media</th><th>Picco</th></tr></thead><tbody>${a.summary.map((m) => `<tr><td>${esc(m.label)}</td><td>${esc(m.name)}</td><td>${esc(m.direction)}</td><td>${number(m.samples)}</td><td>${number(m.mean)} ${esc(m.unit)}</td><td>${number(m.maximum)} ${esc(m.unit)}</td></tr>`).join("")}</tbody></table></div>` : empty("Nessun report RTCP attribuito", "Controlla la copertura nelle sorgenti e le eventuali metriche KPE nel grafico.")}</div></div><div class="panel"><div class="panel-head"><h2>Sequenza SIP</h2><span class="muted">${a.signaling.length} messaggi${a.truncated ? " · primi 500" : ""}</span></div><div class="table-wrap"><table><thead><tr><th>Orario del log</th><th>Sorgente</th><th>Verso</th><th>Messaggio</th><th>Evidenza</th></tr></thead><tbody>${a.signaling.map((e) => `<tr><td class="mono nowrap">${stamp(e.ts)}</td><td>${esc(e.label)}</td><td>${e.direction === "incoming" ? "← ricevuto" : "→ inviato"}</td><td class="mono">${esc(e.title)}<div class="muted">${esc(e.method)}</div></td><td class="mono">${esc(e.filename)}:${e.line_no} · #${e.id}</td></tr>`).join("")}</tbody></table></div></div>`;
}
function renderSQL(page) {
  page.innerHTML =
    title(
      "ESPLORAZIONE LIBERA",
      "Fai domande ai tuoi log.",
      "SQL in sola lettura sul database locale. Massimo 1.000 righe e 3 secondi per query.",
    ) +
    `<div class="panel"><div class="panel-body"><div class="sql-presets">${Object.keys(
      presets,
    )
      .map((p, i) => `<button data-preset="${i}">${p}</button>`)
      .join(
        "",
      )}</div><textarea id="sql" class="sql-input" aria-label="Query SQL" spellcheck="false">${esc(Object.values(presets)[0])}</textarea><div class="actions"><button id="sql-run" class="primary">Esegui query →</button></div></div></div><div id="sql-result"></div><div class="panel"><div class="panel-body schema">calls ← perspectives → imports → files<br>calls / perspectives ← events → files<br>metrics → events / calls / perspectives<br>conversations → conversation_calls → calls<br><br>metrics.valid = 0: valore anomalo · call_id IS NULL: attribuzione non dimostrabile<br>metriche KPE: unit = 'raw' finché l’unità non è documentata</div></div>`;
  $$("[data-preset]").forEach(
    (b) =>
      (b.onclick = () =>
        ($("#sql").value = Object.values(presets)[+b.dataset.preset])),
  );
  $("#sql-run").onclick = safe(async () => {
    const button = $("#sql-run");
    button.disabled = true;
    try {
      const result = await post("query", { sql: $("#sql").value });
      $("#sql-result").innerHTML =
        `<div class="panel"><div class="panel-head"><h2>Risultato</h2><span class="muted">${result.rows.length} righe${result.truncated ? " · risultato troncato" : ""}</span></div><div class="table-wrap"><table><thead><tr>${result.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${result.rows.map((r) => `<tr>${r.map((v) => `<td class="mono">${esc(v === null ? "NULL" : v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></div>`;
    } finally {
      button.disabled = false;
    }
  });
}
async function renderManualConversations(page, token) {
  const conversations = await api("conversations");
  if (token !== renderToken) return;
  const selected = [...state.selected];
  page.innerHTML =
    title(
      "CORRELAZIONE ESPLICITA",
      "Una conversazione, più chiamate.",
      "Collega le diverse tratte di una conferenza, anche quando un PBX riscrive i Call-ID. L’associazione e l’host sono indicati dall’analista, non dedotti dalla sola vicinanza temporale.",
    ) +
    `<div class="panel"><div class="panel-head"><h2>Nuova conversazione</h2><span class="tag neutral">${selected.length} chiamate selezionate</span></div><div class="panel-body"><form id="conversation-form"><div class="conversation-form"><label>Titolo<input name="title" placeholder="es. Conferenza assistenza · 24 settembre" required maxlength="200"></label><label>App host (se nota)<select name="host"><option value="">Non determinato</option>${state.perspectives
      .filter((p) => state.selected.has(p.call_id))
      .map(
        (p) =>
          `<option value="${p.id}">#${p.call_id} · ${esc(p.label)} · linea ${p.line_id ?? "?"}</option>`,
      )
      .join(
        "",
      )}</select></label><label>Motivazione / evidenza<textarea name="note" placeholder="Perché queste chiamate appartengono alla stessa conversazione?" maxlength="2000"></textarea></label></div><p class="muted">Selezione: ${selected.map((id) => "#" + id).join(", ") || "nessuna · scegli almeno due chiamate nel registro"}</p><div class="actions"><button class="primary" ${selected.length < 2 ? "disabled" : ""}>Salva collegamento</button></div></form></div></div><div class="panel"><div class="panel-head"><h2>Conversazioni salvate</h2></div>${conversations.length ? conversations.map((c) => `<div class="conversation-item"><div><h3>${esc(c.title)}</h3><p>Chiamate ${esc(c.call_ids)} · host ${c.host_perspective_id ? "punto di vista #" + c.host_perspective_id : "non determinato"}</p><p>${esc(c.note)}</p></div><button data-conversation="${c.id}">Confronta →</button></div>`).join("") : empty("Nessun collegamento salvato", "Le singole chiamate restano sempre consultabili nel registro.")}</div>`;
  $("#conversation-form").onsubmit = safe(async (e) => {
    e.preventDefault();
    const f = e.currentTarget;
    await post("conversations", {
      title: f.elements.title.value,
      note: f.elements.note.value,
      host_perspective_id: f.elements.host.value,
      call_ids: selected,
    });
    notice("Conversazione salvata con associazione manuale.");
    return render();
  });
  $$("[data-conversation]").forEach(
    (b) =>
      (b.onclick = safe(() => {
        state.selected = new Set(
          conversations
            .find((c) => c.id === +b.dataset.conversation)
            .call_ids.split(",")
            .map(Number),
        );
        updateSelection();
        return setView("compare");
      })),
  );
}
function showUpload() {
  $("#upload-dialog").showModal();
}
function chooseFiles(files) {
  uploadFiles = [...files];
  $("#upload-files").textContent = uploadFiles
    .map((f) => `${f.name} (${number(f.size / 1048576)} MiB)`)
    .join(" · ");
}
$("#upload-top").onclick = showUpload;
$("#upload-cancel").onclick = () => $("#upload-dialog").close();
$("#dropzone").onclick = () => $("#file-input").click();
$("#dropzone").onkeydown = (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    $("#file-input").click();
  }
};
$("#file-input").onchange = (e) => chooseFiles(e.target.files);
$("#dropzone").ondragover = (e) => e.preventDefault();
$("#dropzone").ondrop = (e) => {
  e.preventDefault();
  chooseFiles(e.dataTransfer.files);
};
$("#upload-form").onsubmit = safe(async (e) => {
  e.preventDefault();
  if (!uploadFiles.length) throw Error("Seleziona almeno uno ZIP");
  const button = $("#upload-submit");
  button.disabled = true;
  $("#upload-cancel").disabled = true;
  let failed = 0;
  try {
    for (let i = 0; i < uploadFiles.length; i++) {
      const file = uploadFiles[i];
      $("#upload-progress").textContent =
        `Importazione ${i + 1}/${uploadFiles.length}: ${file.name}…`;
      try {
        if (file.size > 64 * 1048576) throw Error("ZIP oltre 64 MiB");
        const label = $("#upload-label").value;
        const result = await api("imports", {
          method: "POST",
          headers: {
            "Content-Type": "application/octet-stream",
            "X-Filename": encodeURIComponent(file.name),
            "X-Label": encodeURIComponent(
              label
                ? uploadFiles.length > 1
                  ? label + " · " + file.name
                  : label
                : file.name,
            ),
          },
          body: file,
        });
        notice(
          result.duplicate
            ? `${file.name}: già importato; nessun duplicato creato.`
            : `${file.name}: ${result.calls} chiamate, ${number(result.metrics)} metriche importate.`,
        );
      } catch (err) {
        failed++;
        notice(`${file.name}: ${err.message}`, true);
      }
    }
    await refresh();
    await setView("calls");
    $("#upload-progress").textContent = failed
      ? `${failed} archivi non importati. Controlla il messaggio di errore.`
      : "Importazione completata.";
    if (!failed) {
      $("#upload-dialog").close();
      chooseFiles([]);
    }
  } finally {
    button.disabled = false;
    $("#upload-cancel").disabled = false;
  }
});
$$("nav button").forEach(
  (b) => (b.onclick = safe(() => setView(b.dataset.view))),
);
safe(async () => {
  await refresh();
  await render();
})();
