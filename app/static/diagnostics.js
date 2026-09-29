"use strict";
let metricGuideQuery = '';
async function renderCatalog(page, token) {
  const [entries, media] = await Promise.all([api('catalog'), api('media-semantics')]);
  if (token !== renderToken) return;
  page.innerHTML = title('DOCUMENTAZIONE DEL SISTEMA', 'Capire ogni metrica', 'Origine, unità, calcolo e limiti: una guida consultabile anche senza log importati.') +
    `<div class="panel diagnostic-panel"><p>Downstream: media dal peer/GW ricevuto dall’app (incoming). Upstream: media inviato dall’app, la cui ricezione è riportata dal peer/GW nei Receiver Report (outgoing). RTT è bidirezionale. Per xcoder o tratte non identificate si mantengono ricezione locale e del peer; non si invertono le etichette automaticamente. Senza ruolo dichiarato la sorgente è trattata come app presunta. A e B sono le prospettive scelte dall’analista. Flow e SSRC diversi restano serie separate.</p><p>I timestamp originali non dichiarano un fuso. L’offset configurato nelle sorgenti modifica solo l’asse temporale. Assenza di campioni significa dato mancante, mai zero. Valori negativi o percentuali fuori 0–100 sono conservati ma esclusi. Le statistiche KPE last/avg/min/max sono quelle del motore; la media della piattaforma è aritmetica fra campioni.</p><details><summary>Media plane VDK: gerarchia, thread e flussi</summary><p>${esc(media.basis)}</p><table><thead><tr><th>Device</th><th>Classe padre</th><th>Denominazione e ruolo</th></tr></thead><tbody>${media.devices.map(d=>`<tr><td>${esc(d.name)}</td><td>${esc(d.parent || "—")}</td><td>${esc(d.expanded)} — ${esc(d.role)}</td></tr>`).join("")}</tbody></table><ul>${media.rules.map(r=>`<li>${esc(r)}</li>`).join("")}</ul><dl>${Object.entries(media.context).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></details><label>Cerca metrica<input id="catalog-search" placeholder="RTT, buffer, silence…"></label></div><div id="catalog-items"></div>`;
  const draw = () => {
    const query = $('#catalog-search').value.toLowerCase();
    $('#catalog-items').innerHTML = entries.filter(e => JSON.stringify(e).toLowerCase().includes(query)).map(e => `<article class="panel diagnostic-panel metric-doc"><h2>${esc(e.title)}</h2><code>${esc(e.name)}</code> <span class="tag">${esc(e.unit)}</span><p>${esc(e.meaning)}</p><dl><dt>Ambito della misura</dt><dd>${esc(e.semantics?.domain_label || "Non confermato")} — ${esc(e.semantics?.scope || "")}</dd><dt>Origine e conversione</dt><dd>${esc(e.source)}</dd><dt>Tipo di osservazione</dt><dd>${esc(e.kind)}</dd><dt>Interpretazione e limiti</dt><dd>${esc(e.limits)}</dd></dl></article>`).join('');
  };
  $('#catalog-search').value = metricGuideQuery; metricGuideQuery = '';
  $('#catalog-search').oninput = draw; draw();
}
function diagTime(t) { return new Date(t*1000).toISOString().slice(11,23); }
function diagEvidence(value) {
 return (Array.isArray(value)?value:[value]).map(e=>`evento ${e.event_id} · ${esc(e.filename)}:${e.line}`).join('<br>');
}
async function renderManual(page, token) {
  const imports=await api('imports');
  if(token!==renderToken)return;
  page.innerHTML=title('LOG SENZA SEGNALAZIONE', 'File e finestre manuali', 'Per i casi in cui sono disponibili soltanto VDlog e rtplog: importa un dispositivo alla volta, poi delimita la chiamata.')+`<div class="panel diagnostic-panel"><h2>Importa file testuali dello stesso dispositivo</h2><form id="text-form"><label>Dispositivo<input id="text-label" required maxlength="120" placeholder="Lato A"></label><label>File VDlog / rtplog<input type="file" id="text-files" multiple accept=".txt,.log,.old" required></label><p class="muted">Non rinominare i prefissi VDlog e rtplog. Seleziona insieme i file dello stesso lato; ripeti per l’altro lato. Massimo 40 MiB per file e 64 MiB per richiesta JSON.</p><button class="primary">Importa file</button></form></div><div class="panel diagnostic-panel"><h2>Definisci una finestra di chiamata</h2><p>La finestra è un’annotazione dell’analista, non una chiamata ricostruita da SIP. Attribuisce soltanto metriche ancora libere sulla linea indicata. Sono vietate sovrapposizioni con altre finestre della stessa linea.</p><form id="window-form"><div class="diagnostic-controls"><label>Sorgente<select id="window-import">${imports.map(i=>`<option value="${i.id}">${esc(i.label)} · #${i.id}</option>`).join('')}</select></label><label>Titolo<input id="window-title" value="Finestra manuale" maxlength="200"></label><label>Linea<input id="window-line" type="number" min="0" value="0" required></label><label>Inizio (orario originale)<input id="window-start" type="datetime-local" step="0.001" required></label><label>Fine (orario originale)<input id="window-end" type="datetime-local" step="0.001" required></label></div><button class="primary">Crea finestra</button></form><p class="muted">Gli orari devono coincidere con quelli dei file. Per due lati, crea una finestra in ciascuna sorgente e seleziona entrambe in Diagnostica A/B. Il collegamento non implica che siano lo stesso dialogo SIP.</p></div>`;
  page.insertAdjacentHTML('beforeend','<div class="panel diagnostic-panel" id="window-editor"></div>');
  await mountWindowEditor($('#window-editor'),token);
  if(token!==renderToken)return;
  $('#text-form').onsubmit=safe(async e=>{
    e.preventDefault();const selected=[...$('#text-files').files];
    if(!selected.length||selected.length>20||selected.some(f=>f.size>40*1024*1024))throw Error('Seleziona da 1 a 20 file, massimo 40 MiB ciascuno');
    const payload={label:$('#text-label').value,files:await Promise.all(selected.map(async f=>({name:f.name,text:await f.text()})))};
    if(new Blob([JSON.stringify(payload)]).size>64*1024*1024)throw Error('Richiesta oltre 64 MiB: importa uno ZIP');
    const result=await post('text-import',payload);notice(result.duplicate?'File già importati.':'File importati; definisci la finestra se non sono state ricostruite chiamate.');await refresh();if(token===renderToken)await render();
  });
  $('#window-form').onsubmit=safe(async e=>{e.preventDefault();const result=await post('windows',{import_id:$('#window-import').value,line_id:$('#window-line').value,start:$('#window-start').value,end:$('#window-end').value,title:$('#window-title').value});notice('Finestra creata: chiamata #'+result.call_id);await refresh();if(token===renderToken)await setView('diagnostics');});
}
