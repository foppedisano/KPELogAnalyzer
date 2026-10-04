"use strict";
async function renderAnalytics(page, token) {
  const [catalog, saved, coverage] = await Promise.all([
    api("analytics/catalog"), api("analytics/recipes"), api("analytics/coverage"),
  ]);
  if (token !== renderToken) return;
  let recipe = null, last = null;
  page.innerHTML = title("LABORATORIO ANALITICO", "Domande nuove, evidenze verificabili.",
    "Componi analisi sui dati disponibili oppure collegati da un coding agent via MCP. Ogni risultato conserva query, parametri, copertura e versione del modello.") +
    `<div class="panel analytics-panel"><div class="panel-body"><div class="actions">
    <label>Esempio<select id="analytics-example">${catalog.examples.map((e,i)=>`<option value="${i}">${esc(e.title)}</option>`).join("")}</select></label>
    <button id="analytics-load-example">Carica esempio</button>
    <label>Analisi salvata<select id="analytics-saved"><option value="">Scegli una ricetta</option>${saved.items.map(r=>`<option value="${r.id}">${esc(r.title)} · v${r.revision}</option>`).join("")}</select></label>
    <button id="analytics-load-saved">Carica ricetta</button></div>
    <label>Nome dell’analisi<input id="analytics-title" maxlength="200"></label>
    <label>Domanda e criteri<textarea id="analytics-question" rows="2" maxlength="4000"></textarea></label>
    <label>SQL sulle viste del catalogo<textarea id="analytics-sql" class="sql-input" spellcheck="false"></textarea></label>
    <div class="actions"><label>Parametri JSON<textarea id="analytics-parameters" rows="3" spellcheck="false">{}</textarea></label>
    <label>Selezione JSON (vuota = tutte le chiamate)<textarea id="analytics-scope" rows="3" spellcheck="false">{}</textarea></label></div>
    <div class="actions"><label class="analytics-check"><input type="checkbox" id="analytics-mos"> Calcola intervalli ed episodi MOS</label>
    <label class="analytics-check"><input type="checkbox" id="analytics-incidents"> Calcola episodi audio e finestre</label>
    <label class="analytics-check"><input type="checkbox" id="analytics-incident-summary"> Riepilogo episodi dell’archivio</label>
    <label class="analytics-check"><input type="checkbox" id="analytics-transients"> Confronta contatori e transitori</label>
    <label>Tolleranza transitori (s)<input id="analytics-tolerance" type="number" value="0" min="0" max="30" step="0.1"></label>
    <label>Finestra episodi (s)<input id="analytics-window" type="number" value="1" min="0.001" max="3600" step="0.001"></label>
    <label>Collocazione underrun<select id="analytics-placement"><option value="reported_end">Durata dichiarata, ancorata alla fine</option><option value="log_span">Timestamp dei messaggi</option></select></label>
    <label>MOS scarso sotto<input id="analytics-threshold" type="number" value="3" min="1" max="5" step="0.1"></label>
    <label>Durata minima episodio (s)<input id="analytics-minimum" type="number" value="0" min="0" max="86400"></label>
    <label>Massimo righe<input id="analytics-limit" type="number" value="200" min="1" max="1000"></label></div>
    <p class="muted">Media MOS pesata per durata. Gli episodi restano separati per ricevitore e flusso. Dati mancanti ≠ buona qualità.</p>
    <div class="actions"><button id="analytics-run" class="primary">Esegui analisi →</button><button id="analytics-save">Salva nuova ricetta</button><button id="analytics-update" disabled>Aggiorna ricetta</button><button id="analytics-export" disabled>Esporta risultato JSON</button></div>
    <p id="analytics-status" role="status"></p></div></div><div id="analytics-result"></div>
    <details class="panel"><summary>Catalogo delle viste e regole di lettura</summary><div class="panel-body">
    <p>Le viste a_mos* richiedono il calcolo MOS; a_incident* il calcolo episodi audio. Per gli episodi selezionare le chiamate nello scope. Scope: <code>{"call_ids":[1],"start":"2026-01-01 00:00:00","end":"2026-02-01 00:00:00"}</code>. Nessuna conversione implicita del fuso orario.</p>
    ${Object.entries(catalog.tables).map(([name,t])=>`<details><summary><code>${esc(name)}</code> · ${esc(t.description)}</summary><p class="mono">${t.columns.map(c=>esc(c.name)+" "+esc(c.type)).join(" · ")}</p></details>`).join("")}
    <ul>${catalog.rules.map(r=>`<li>${esc(r)}</li>`).join("")}</ul></div></details>
    <details class="panel"><summary>Disponibilità dei dati</summary><pre class="panel-body">${esc(JSON.stringify(coverage,null,2))}</pre></details>`;
  const el = id => page.querySelector("#analytics-"+id);
  function load(definition, title, question) {
    el("title").value=title;el("question").value=question||"";
    el("sql").value=definition.sql;
    el("parameters").value=JSON.stringify(definition.parameters||{},null,2);
    el("scope").value=JSON.stringify(definition.scope||{},null,2);
    el("mos").checked=(definition.datasets||[]).includes("mos");
    el("incidents").checked=(definition.datasets||[]).includes("incidents");el("window").value=definition.incident_window_seconds??1;el("placement").value=definition.incident_time_basis||"reported_end";
    el("incident-summary").checked=(definition.datasets||[]).includes("incident_summary");
    el("transients").checked=(definition.datasets||[]).includes("transients");el("tolerance").value=definition.transient_tolerance_seconds??0;
    el("threshold").value=definition.threshold??3;el("minimum").value=definition.min_episode_seconds??0;
    el("limit").value=definition.limit??200;el("update").disabled=!recipe;
    el("status").textContent=recipe?`Ricetta #${recipe.id} · revisione ${recipe.revision}`:"Nuova analisi";
    el("result").replaceChildren();last=null;el("export").disabled=true;
  }
  const definition=()=>({sql:el("sql").value,parameters:JSON.parse(el("parameters").value),scope:JSON.parse(el("scope").value),
    datasets:[...(el("mos").checked?["mos"]:[]),...(el("incidents").checked?["incidents"]:[]),...(el("incident-summary").checked?["incident_summary"]:[]),...(el("transients").checked?["transients"]:[])],transient_tolerance_seconds:+el("tolerance").value,incident_window_seconds:+el("window").value,incident_time_basis:el("placement").value,threshold:+el("threshold").value,min_episode_seconds:+el("minimum").value,limit:+el("limit").value});
  el("load-example").onclick=()=>{recipe=null;const e=catalog.examples[+el("example").value];load(e,e.title);};
  el("load-saved").onclick=()=>{const found=saved.items.find(r=>r.id===+el("saved").value);if(found){recipe=found;load(found.definition,found.title,found.question);}};
  async function busy(action) {
    const buttons=["run","save","update","load-example","load-saved"].map(el);buttons.forEach(b=>b.disabled=true);
    el("status").textContent="Elaborazione in corso…";
    try {await action();} catch(e) {if(token===renderToken)el("status").textContent=e.message;}
    finally {if(token===renderToken){buttons.forEach(b=>b.disabled=false);el("update").disabled=!recipe;}}
  }
  el("run").onclick=()=>busy(async()=>{
    const request=definition();last=null;el("export").disabled=true;el("result").replaceChildren();
    const result=await post("analytics/query",request);if(token!==renderToken)return;last=result;el("export").disabled=false;
    el("status").textContent=`${result.rows.length} righe · ${result.elapsed_ms} ms${result.truncated?" · RISULTATO TRONCATO":""}`;
    el("result").innerHTML=`<div class="panel"><div class="panel-body"><h2>Risultato dell’analisi</h2><p>${result.coverage.selected_calls} chiamate selezionate · ${result.coverage.observations} prospettive · ${result.coverage.calls_with_mos} chiamate con MOS · ${result.coverage.mos_intervals} intervalli MOS · ${result.coverage.incident_episodes} episodi audio · ${result.coverage.incident_windows} finestre audio</p><p class="muted">${result.warnings.map(esc).join(" ")}</p></div><div class="table-wrap"><table><thead><tr>${result.columns.map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${result.rows.map(row=>`<tr>${row.map(v=>`<td title="${esc(v)}">${esc(v===null?"—":typeof v==="number"?number(v):v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></div>`;
  });
  async function save(update) {
    const payload={title:el("title").value,question:el("question").value,interpretation:recipe?.interpretation||"",definition:definition()};
    if(update)Object.assign(payload,{id:recipe.id,revision:recipe.revision});
    const result=await post("analytics/recipes",payload,update?"PATCH":"POST");if(token!==renderToken)return;
    recipe={...payload,...result};const index=saved.items.findIndex(r=>r.id===recipe.id);
    if(index<0)saved.items.push(recipe);else saved.items[index]=recipe;
    el("saved").innerHTML=`<option value="">Scegli una ricetta</option>`+saved.items.map(r=>`<option value="${r.id}">${esc(r.title)} · v${r.revision}</option>`).join("");
    el("saved").value=String(recipe.id);el("status").textContent=`Salvata ricetta #${recipe.id} · revisione ${recipe.revision}`;
  }
  el("save").onclick=()=>busy(()=>save(false));el("update").onclick=()=>busy(()=>save(true));
  el("export").onclick=()=>{if(!last)return;const url=URL.createObjectURL(new Blob([JSON.stringify(last,null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="kpe-analisi.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  load(catalog.examples[0],catalog.examples[0].title);
}
