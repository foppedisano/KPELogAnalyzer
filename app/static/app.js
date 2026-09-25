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
    compare: renderCompare,
    sources: renderSources,
    logs: renderLogs,
    sql: renderSQL,
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
  return `<div class="stats"><div class="stat"><span>Chiamate ricostruite</span><strong>${number(o.calls)}</strong><small>Identità SIP e sessioni locali</small></div><div class="stat"><span>Archivi importati</span><strong>${number(o.imports)}</strong><small>Punti di vista indipendenti</small></div><div class="stat"><span>Campioni metrici</span><strong>${number(o.metrics)}</strong><small>${number(o.unassigned_metrics)} non attribuiti</small></div><div class="stat"><span>Eventi indicizzati</span><strong>${number(o.events)}</strong><small>Con file e riga di origine</small></div></div>`;
}
function callTable(calls) {
  return `<div class="table-wrap"><table><thead><tr><th aria-label="Seleziona"></th><th>Chiamata / interlocutori</th><th>Stato osservato</th><th>Durata connessa</th><th>Prospettive</th><th>Metriche</th></tr></thead><tbody>${calls.map((c) => `<tr class="call-row" data-id="${c.id}" tabindex="0"><td><input type="checkbox" class="call-check" aria-label="Seleziona chiamata ${c.id}" value="${c.id}" ${state.selected.has(c.id) ? "checked" : ""}></td><td><div class="identity" title="${esc(c.caller + " → " + c.callee)}">${esc(shortIdentity(c.caller))} <span class="muted">→</span> ${esc(shortIdentity(c.callee))}</div><div class="call-date">${stamp(c.start)} <span class="muted">· #${c.id}</span></div></td><td><span class="tag ${c.status.includes("failed") ? "warn" : c.status.includes("partial") ? "neutral" : ""}">${esc(c.status)}</span></td><td class="mono nowrap">${duration(c)}</td><td>${c.perspectives} <span class="muted">sorgenti</span></td><td class="mono">${number(c.metrics)}</td></tr>`).join("")}</tbody></table></div>`;
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
    `<div class="panel"><div class="panel-head"><h2>Registro chiamate</h2><div class="toolbar"><input id="call-search" aria-label="Cerca chiamate" placeholder="Cerca interlocutore o Call-ID…"><button id="compare-selected">Confronta selezionate →</button></div></div><div id="call-list"></div><div class="table-note">Orari originali dei log, senza fuso dichiarato. Seleziona più righe per confrontare chiamate o partecipanti. Massimo 2.000 chiamate elencate.</div></div>`;
  function list() {
    const text = $("#call-search").value.toLowerCase();
    const calls = state.calls.filter((c) =>
      (c.caller + c.callee + c.sip_call_id).toLowerCase().includes(text),
    );
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
    `<div class="detail-meta"><div><span>PRIMA EVIDENZA</span><strong>${stamp(c.start)}</strong></div><div><span>CONNESSIONE</span><strong>${stamp(c.connected)}</strong></div><div><span>ULTIMA TERMINAZIONE</span><strong>${stamp(c.end)}</strong></div><div><span>DURATA CONNESSA*</span><strong>${duration(c)}</strong></div></div><p class="mono muted">Call-ID: ${esc(c.sip_call_id || "Non disponibile · sessione locale")}</p><p class="muted">* Intervallo osservato; con più sorgenti non corregge eventuali differenze tra gli orologi.</p><div class="panel"><div class="panel-head"><h2>Punti di vista</h2><span class="tag neutral">${ps.length} sorgenti</span></div>${ps.map((p) => `<div class="perspective"><strong>${esc(p.label)} <span class="tag neutral">${esc(p.direction)}</span> <span class="tag">${esc(p.status)}</span></strong><small>App ${esc(p.app_version || "versione non documentata")} ${p.version_event_id ? "(evento " + p.version_event_id + ")" : ""} · Linea ${p.line_id ?? "non nota"} · ${esc(p.evidence)} · offset grafico ${p.clock_offset}s</small><small>${stamp(p.start)} → ${stamp(p.end)}</small></div>`).join("")}</div><div id="analysis-panel"></div><div id="chart-panel"></div><div id="detail-events"></div>`;
  $("#back-calls").onclick = safe(() => setView("calls"));
  $("#select-detail").onclick = () => {
    state.selected.has(id) ? state.selected.delete(id) : state.selected.add(id);
    updateSelection();
    $("#select-detail").textContent = state.selected.has(id)
      ? "Rimuovi dal confronto"
      : "Aggiungi al confronto";
  };
  await mountChart($("#chart-panel"), [id]);
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
async function mountChart(root, ids) {
  if (!root) return;
  root.innerHTML = `<div class="panel"><div class="panel-head"><h2>Andamento delle metriche</h2><a id="csv-link" class="small-button">↓ CSV</a></div><div class="panel-body"><div class="chart-controls"><label>Parametro<select id="metric-name"></select></label><label>Statistica<select id="metric-stat"></select></label><label>Allineamento<select id="chart-axis"><option value="relative">Tempo dalla prima evidenza</option><option value="absolute">Orario log + correzione</option></select></label><label class="check"><input type="checkbox" id="include-invalid"> Mostra anomali</label></div><p class="muted" id="unit-note"></p><div class="chart-area"><canvas id="chart" aria-label="Grafico temporale delle metriche" role="img"></canvas><div class="chart-tooltip" hidden></div></div><div id="chart-legend" class="legend"></div><div class="toolbar"><button class="small-button" id="reset-zoom">Ripristina zoom</button><small>Rotella per ingrandire · passa sui campioni per leggere il valore</small></div><div id="metric-summary" class="metric-summary"></div><div id="metric-episodes"></div><p class="muted">Le somme A+B richiedono due sorgenti esplicite: usa Diagnostica A/B. Le voci del catalogo senza campioni restano selezionabili.</p></div></div>`;
  const names = [...new Set(state.metrics.map((m) => m.name))];
  $("#metric-name", root).innerHTML = names
    .map((n) => `<option>${esc(n)}</option>`)
    .join("");
  if (names.includes("rtcp.rtt")) $("#metric-name", root).value = "rtcp.rtt";
  let request = 0,
    points = [],
    hidden = new Set(),
    zoom = null;
  const canvas = $("#chart", root),
    tooltip = $(".chart-tooltip", root);
  let drawn = [],
    bounds = null;
  function statsOptions() {
    const n = $("#metric-name", root).value;
    $("#metric-stat", root).innerHTML = state.metrics
      .filter((m) => m.name === n)
      .map((m) => `<option>${esc(m.statistic)}</option>`)
      .join("");
    if (state.metrics.some((m) => m.name === n && m.statistic === "last"))
      $("#metric-stat", root).value = "last";
  }
  function seriesKey(p) {
    return `#${p.call_id} · P${p.perspective_id} · ${p.label} · ${p.direction} · flusso ${p.flow}${p.ssrc ? " · " + p.ssrc : ""}${p.device ? " · " + p.device : ""} · ${p.sample_kind}${p.observer ? " · " + p.observer : ""}`;
  }
  function series() {
    const groups = new Map();
    for (const p of points) {
      const key = seriesKey(p);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(p);
    }
    return [...groups.entries()];
  }
  function draw() {
    if (!canvas.isConnected) return;
    const rect = canvas.getBoundingClientRect(),
      w = rect.width,
      h = rect.height,
      dpr = window.devicePixelRatio || 1;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    const left = 65,
      right = w - 18,
      top = 24,
      bottom = h - 38;
    ctx.font = "10px Segoe UI";
    ctx.fillStyle = "#82929f";
    drawn = [];
    const absolute = $("#chart-axis", root).value === "absolute";
    const groups = series();
    const visible = groups.filter(([k]) => !hidden.has(k));
    let all = visible.flatMap(([, ps]) =>
      ps.map((p) => ({
        ...p,
        x: absolute
          ? timeValue(p.ts) + p.clock_offset * 1000
          : timeValue(p.ts) - timeValue(p.start),
      })),
    );
    if (!all.length) {
      ctx.textAlign = "center";
      ctx.fillText(
        "Nessun campione disponibile per questa selezione",
        w / 2,
        h / 2,
      );
      bounds = null;
      return;
    }
    let xmin = Infinity,
      xmax = -Infinity;
    for (const p of all) {
      xmin = Math.min(xmin, p.x);
      xmax = Math.max(xmax, p.x);
    }
    if (xmin === xmax) xmax = xmin + 1000;
    if (zoom) {
      [xmin, xmax] = zoom;
    }
    all = all.filter((p) => p.x >= xmin && p.x <= xmax);
    let ymin = 0,
      ymax = 0;
    for (const p of all) {
      ymin = Math.min(ymin, p.value);
      ymax = Math.max(ymax, p.value);
    }
    if (ymin === ymax) ymax = ymin + 1;
    ymax += (ymax - ymin) * 0.1;
    const sx = (x) => left + ((x - xmin) / (xmax - xmin)) * (right - left),
      sy = (y) => bottom - ((y - ymin) / (ymax - ymin)) * (bottom - top);
    bounds = { xmin, xmax, left, right };
    for (let i = 0; i <= 4; i++) {
      const y = top + ((bottom - top) * i) / 4;
      ctx.strokeStyle = "#eaf0f3";
      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(right, y);
      ctx.stroke();
      ctx.textAlign = "right";
      ctx.fillStyle = "#82929f";
      ctx.fillText(number(ymax - ((ymax - ymin) * i) / 4), left - 10, y + 3);
    }
    for (let i = 0; i <= 4; i++) {
      const value = xmin + ((xmax - xmin) * i) / 4;
      ctx.textAlign = "center";
      ctx.fillText(
        absolute
          ? new Date(value).toISOString().slice(11, 19)
          : number(value / 1000) + " s",
        sx(value),
        h - 12,
      );
    }
    groups.forEach(([key, ps], idx) => {
      if (hidden.has(key)) return;
      ctx.strokeStyle = colors[idx % colors.length];
      ctx.fillStyle = colors[idx % colors.length];
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      let last = null;
      for (const p of ps) {
        const x = absolute
          ? timeValue(p.ts) + p.clock_offset * 1000
          : timeValue(p.ts) - timeValue(p.start);
        if (x < xmin || x > xmax) continue;
        const px = sx(x),
          py = sy(p.value);
        if (last === null || x - last > 30000 || ['event','interval','episode'].includes(p.sample_kind)) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
        last = x;
        drawn.push({ px, py, p, key });
      }
      ctx.stroke();
      for (const d of drawn.filter((d) => d.key === key)) {
        ctx.beginPath();
        ctx.arc(d.px, d.py, d.p.valid ? 2 : 4, 0, Math.PI * 2);
        ctx.fill();
      }
    });
  }
  function updateSummary() {
    const visible = points.filter((p) => !hidden.has(seriesKey(p)));
    let min = Infinity,
      max = -Infinity,
      sum = 0;
    for (const p of visible) {
      min = Math.min(min, p.value);
      max = Math.max(max, p.value);
      sum += p.value;
    }
    $("#metric-summary", root).innerHTML =
      `<div>CAMPIONI<strong>${number(visible.length)}</strong></div><div>MIN<strong>${visible.length ? number(min) : "—"}</strong></div><div>MEDIA DEI CAMPIONI<strong>${visible.length ? number(sum / visible.length) : "—"}</strong></div><div>MAX<strong>${visible.length ? number(max) : "—"}</strong></div><div>UNITÀ<strong>${esc(visible[0]?.unit || "—")}</strong></div>`;
  }
  async function load() {
    const ticket = ++request;
    const params = new URLSearchParams({
      calls: ids.join(","),
      name: $("#metric-name", root).value,
      statistic: $("#metric-stat", root).value,
      invalid: $("#include-invalid", root).checked ? "1" : "0",
    });
    $("#csv-link", root).href = "/api/metrics?" + params + "&format=csv";
    const data = await api("metrics?" + params);
    if (ticket !== request || !root.isConnected) return;
    points = data.filter(p=>p.value!==null && Number.isFinite(p.value));
    const episodes=data.filter(p=>p.episode).map(p=>({...p.episode,side:`P${p.perspective_id} · ${p.label}`}));
    $("#metric-episodes",root).innerHTML=episodes.length?incidentTable({incidents:episodes,incident_warnings:[]}):"";
    hidden.clear();
    zoom = null;
    const unit = points[0]?.unit;
    $("#unit-note", root).textContent =
      unit === "raw"
        ? "Unità KPE non dichiarata: valori originali, senza conversione. last / avg / min / max sono statistiche emesse dal motore."
        : "RTCP usa le unità esplicite del log. Il ping ICMP misura un endpoint di rete, non la latenza audio. I vuoti oltre 30 s interrompono le linee.";
    if(params.get('name')==='vd.missing_packets') $('#unit-note',root).textContent='Pacchetti mancanti dichiarati per evento NART: punti isolati, non percentuale e non perdita definitiva. Non sommare segnalazioni come pacchetti unici persi; consulta il messaggio originale.';
    if(params.get('name')==='derived.silence_delta') $('#unit-note',root).textContent='Incremento tra due campioni dello stesso contatore/device/flusso, in ms. Punti isolati al secondo campione; primo valore, reset e intervalli oltre 30 s sono omessi. Entrambi i campioni sono nel tooltip e nel CSV.';
    if(params.get('name').startsWith('incident.')) $('#unit-note',root).textContent='Durata degli episodi al momento della segnalazione (punti isolati). Il tooltip distingue durata dichiarata e minimo stimato. Durate ignote non diventano zero e restano nella tabella. Orari della tabella originali; offset solo sul grafico.';
    if(!data.length) $('#unit-note',root).textContent+=' Nessun campione calcolabile/disponibile nelle chiamate selezionate.';
    $("#chart-legend", root).innerHTML = series()
      .map(
        ([key], i) =>
          `<button data-series="${i}"><span class="series-dot">●</span>${esc(key)}</button>`,
      )
      .join("");
    $$("#chart-legend button", root).forEach((b, i) => {
      const dot = $(".series-dot", b); // SVG swatches avoid inline styles under CSP.
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("width", "10");
      svg.setAttribute("height", "10");
      const circle = document.createElementNS(svg.namespaceURI, "circle");
      for (const [k, v] of Object.entries({
        cx: 5,
        cy: 5,
        r: 4,
        fill: colors[i % colors.length],
      }))
        circle.setAttribute(k, v);
      svg.append(circle);
      dot.replaceWith(svg);
      b.onclick = () => {
        const key = series()[i][0];
        hidden.has(key) ? hidden.delete(key) : hidden.add(key);
        b.classList.toggle("disabled", hidden.has(key));
        draw();
        updateSummary();
      };
    });
    updateSummary();
    draw();
  }
  statsOptions();
  $("#metric-name", root).onchange = safe(() => {
    statsOptions();
    return load();
  });
  $("#metric-stat", root).onchange = safe(load);
  $("#include-invalid", root).onchange = safe(load);
  $("#chart-axis", root).onchange = () => {
    zoom = null;
    draw();
  };
  $("#reset-zoom", root).onclick = () => {
    zoom = null;
    draw();
  };
  canvas.onwheel = (e) => {
    if (!bounds) return;
    e.preventDefault();
    const f = e.deltaY > 0 ? 1.4 : 0.7,
      anchor = Math.max(
        0,
        Math.min(1, (e.offsetX - bounds.left) / (bounds.right - bounds.left)),
      ),
      center = bounds.xmin + (bounds.xmax - bounds.xmin) * anchor,
      span = (bounds.xmax - bounds.xmin) * f;
    zoom = [center - span * anchor, center + span * (1 - anchor)];
    draw();
  };
  canvas.onmousemove = (e) => {
    let closest = null,
      dist = Infinity;
    for (const d of drawn) {
      const dd = Math.hypot(d.px - e.offsetX, d.py - e.offsetY);
      if (dd < dist) {
        dist = dd;
        closest = d;
      }
    }
    if (!closest || dist > 45) {
      tooltip.hidden = true;
      return;
    }
    const p = closest.p;
    tooltip.textContent = `${number(p.value)} ${p.unit}${p.valid ? "" : " · VALORE ANOMALO"}\n${stamp(p.ts)}\n${closest.key}\n${p.filename}:${p.line_no}`;
    if(p.evidence) tooltip.textContent+='\n'+p.evidence.map(e=>`evento ${e.event_id} · ${e.filename}:${e.line}`).join('\n');
    if(p.interval_seconds) tooltip.textContent+=`\nIntervallo: ${number(p.interval_seconds)} s`;
    if(p.episode) tooltip.textContent+='\n'+incidentDuration(p.episode)+' · '+p.episode.status;
    tooltip.hidden = false;
  };
  canvas.onmouseleave = () => (tooltip.hidden = true);
  const ro = new ResizeObserver(draw);
  ro.observe(canvas);
  chartCleanup = () => {
    request++;
    ro.disconnect();
  };
  await load();
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
      "Controlla copertura e limiti di parsing. La correzione orologio si applica solo al grafico assoluto; i timestamp originali rimangono disponibili.",
    ) +
    `<div class="panel">${
      imports.length
        ? imports
            .map(
              (i) =>
                `<div class="source-card"><form class="source-edit" data-id="${i.id}"><label>Nome dispositivo / sorgente<input name="label" value="${esc(i.label)}" maxlength="120" required></label><label>Correzione orologio (s)<input name="offset" type="number" min="-86400" max="86400" step="0.001" value="${i.clock_offset}"></label><button>Salva</button></form><p class="mono muted">${esc(i.name)} · ${i.file_count} file · ${number(i.event_count)} eventi</p><details><summary>Avvisi di importazione (${JSON.parse(i.warnings).length})</summary><ul>${JSON.parse(
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
async function renderConversations(page, token) {
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
