"use strict";
const groupKinds = {uuid:'Identificatore condiviso',sip:'Stesso Call-ID',manual:'Collegamento manuale',session:'Sessione app / xcoder'};
function sourceDescription(p){
 const s=p.profile||p.source_profile||{};
 return [s.platform==='unknown'?'Piattaforma non documentata':s.platform,s.model,s.os_version?'OS '+s.os_version:'',s.app_version?'App '+s.app_version+' (metadato dell’esportazione)':''].filter(Boolean).join(' · ');
}
async function renderConversations(page,token){
 const [groups,devices,catalog]=await Promise.all([api('conversation-groups'),api('devices'),api('catalog')]);
 if(token!==renderToken)return;
 page.innerHTML=title('OSSERVAZIONI COLLEGATE','Conversazioni','Un’unica conversazione può attraversare app, gateway e più Call-ID. Qui trovi i collegamenti documentati, con gli esiti di ogni tratta.')+`<div class="panel diagnostic-panel"><div class="actions"><input id="group-search" aria-label="Cerca conversazioni" placeholder="Cerca data, Call-ID, sorgente o partecipante…"><label><input id="group-repeated" type="checkbox"> Includi lo stesso Call-ID in più esportazioni</label><button id="group-manual">Collega manualmente</button></div><p class="muted">Gli orari sono quelli dei log. La vicinanza temporale da sola non crea collegamenti. Un log set non equivale necessariamente a una persona.</p><div id="group-count" role="status"></div></div><div id="group-detail"></div><div id="group-list"></div>`;
 $('#group-manual').onclick=safe(async()=>{await renderManualConversations(page,token);page.insertAdjacentHTML('afterbegin','<button id="group-back">← Conversazioni ricostruite</button>');$('#group-back').onclick=safe(()=>render());});
 let active=0;
 function list(){
  const query=$('#group-search').value.toLowerCase(),repeated=$('#group-repeated').checked;
  const shown=groups.filter(g=>(repeated||g.call_ids.length>1||['manual','session'].includes(g.kind))&&JSON.stringify(g).toLowerCase().includes(query));
  $('#group-count').textContent=`${shown.length} gruppi · ${groups.filter(g=>g.call_ids.length>1).length} con più Call-ID`;
  $('#group-list').innerHTML=shown.map(g=>`<div class="panel conversation-item"><div><span class="tag neutral">${esc(groupKinds[g.kind])}</span> ${g.review?'<span class="tag">Da verificare: identificatore ambiguo</span>':''}<h2>${esc(g.title)}</h2><p>${esc(stamp(g.start))} → ${esc(stamp(g.end))}</p><p>${g.call_ids.length} chiamate · ${g.perspectives.length} osservazioni · ${g.source_count} log set · ${esc([...new Set(g.perspectives.map(p=>p.profile.platform))].join(' / '))}</p><p>${esc([...new Set(g.perspectives.map(p=>p.participant||shortIdentity(p.caller)+' → '+shortIdentity(p.callee)))].join(' · '))}</p></div><button data-group="${esc(g.key)}">Esplora →</button></div>`).join('')||empty('Nessun collegamento disponibile','Importa i log dell’altro lato oppure seleziona le chiamate nel registro e collegale manualmente con una nota.');
  $$('[data-group]').forEach(b=>b.onclick=safe(()=>groupDetail(groups.find(g=>g.key===b.dataset.group))));
 }
 $('#group-search').oninput=list;$('#group-repeated').onchange=list;list();
 async function groupDetail(g){
  ++active;if(chartCleanup){chartCleanup();chartCleanup=null;}
  const chosen=new Set(),seen=new Set();
  // Prefer the richest snapshot of each Call-ID; the analyst can select additional sources.
  [...g.perspectives].sort((a,b)=>b.metrics-a.metrics).forEach(p=>{if(!seen.has(p.call_id)){chosen.add(p.id);seen.add(p.call_id);}});
  $('#group-detail').innerHTML=`<div class="panel diagnostic-panel"><button id="group-close">Chiudi dettaglio</button><h2>${esc(g.title)}</h2><p>${esc(g.note)}</p>${g.review?'<p class="inline-note">Identificatore riutilizzato o più identificatori per la stessa chiamata: il gruppo è un candidato da verificare, non una conversazione confermata.</p>':''}<div class="conversation-legs">${g.perspectives.map(p=>`<article class="source-card"><label><input class="group-p" type="checkbox" value="${p.id}" ${chosen.has(p.id)?'checked':''}> <strong>${esc(p.participant||p.label)} · ${esc(p.role||'ruolo non classificato')}</strong></label><p><span class="tag">${esc(p.display_status==='answered_elsewhere'?'Risposta altrove':p.display_status)}</span> · Chiamata #${p.call_id} / P${p.id}</p><p>${esc(sourceDescription(p))}</p><p>${esc(stamp(p.start))} → ${esc(stamp(p.end))}</p><p>${number(p.metrics)} metriche attribuite · ${p.line_id==null?'linea non ricostruita':'linea '+p.line_id}</p><p class="muted">${p.profile.has_periodic_callinfo?'File CallInfo presente.':'File CallInfo assente: le statistiche KPE possono essere solo riepiloghi finali.'} ${!p.metrics?'Nessun campione attribuito: controllare copertura e finestre; non significa assenza di problemi.':''}</p><details><summary>Identità SIP e sorgente</summary><p class="mono">${esc(p.sip_call_id)}</p><p>${esc(p.import_name)}</p>${p.outcomes.map(o=>`<p>Risposta altrove: evento ${o.event_id} · ${esc(o.filename)}:${o.line_no}</p>`).join('')}</details><label>Device VD<select id="group-device-${p.id}">${[...new Set(devices.filter(d=>d.perspective_id===p.id).map(d=>d.device))].map(d=>`<option>${esc(d)}</option>`).join('')||'<option>NART0 of Line 0</option>'}</select></label><button data-leg="${p.call_id}">Apri chiamata #${p.call_id}</button></article>`).join('')}</div><details><summary>Prove del collegamento (${g.evidence.length})</summary>${g.evidence.length?g.evidence.map(e=>`<p class="mono">${esc(e.uuid)} · chiamata #${e.call_id} · evento ${e.event_id} · ${esc(e.filename)}:${e.source_line}</p>`).join(''):'<p>'+esc(g.note)+'</p>'}</details><p>Preselezionata l’osservazione con più metriche per ogni Call-ID: verifica i log da confrontare, specialmente se sono esportazioni ripetute. Puoi includere fino a 16 osservazioni, anche app e xcoder.</p><div class="diagnostic-controls"><label>Inizio corretto<input id="group-start" type="datetime-local" step="0.001"></label><label>Fine corretta<input id="group-end" type="datetime-local" step="0.001"></label></div><button id="group-plot" class="primary">Confronta le osservazioni selezionate</button><div id="group-chart"></div></div>`;
  $('#group-close').onclick=()=>{++active;if(chartCleanup){chartCleanup();chartCleanup=null;}$('#group-detail').innerHTML='';};
  $$('[data-leg]').forEach(b=>b.onclick=safe(()=>detail(+b.dataset.leg)));
  $('#group-detail').scrollIntoView({behavior:'smooth',block:'start'});
  $('#group-plot').onclick=safe(async()=>{
   const run=++active,ids=$$('.group-p:checked').map(x=>+x.value);
   if(!ids.length||ids.length>16)throw Error('Seleziona da 1 a 16 osservazioni');
   const start=$('#group-start').value,end=$('#group-end').value;
   const requests=ids.map(id=>({id,device:$('#group-device-'+id).value}));
   const result={series:[],coverage:[],incidents:[],incident_warnings:[],max_gap_seconds:30,window:{start:null,end:null}};
   if(chartCleanup){chartCleanup();chartCleanup=null;}$('#group-chart').textContent='Caricamento…';
   for(const request of requests){
    const data=await api('diagnostics?'+new URLSearchParams({a:request.id,device_a:request.device,start,end}));
    if(token!==renderToken||run!==active)return;
    const p=g.perspectives.find(p=>p.id===request.id),side=`${p.participant||p.profile.platform} · ${p.role||'app?'} · P${p.id}`;
    for(const key of ['series','coverage','incidents'])result[key].push(...data[key].map(s=>({...s,side})));
    result.incident_warnings.push(...data.incident_warnings.map(w=>side+': '+w));
    if(data.window.start&&(!result.window.start||data.window.start<result.window.start))result.window.start=data.window.start;
    if(data.window.end&&(!result.window.end||data.window.end>result.window.end))result.window.end=data.window.end;
   }
   const config={metrics:[...diagnosticNames],styles:{},silence_unit:'ms'},colors=['#0072b2','#d55e00','#009e73','#cc79a7','#7b3294','#b57600','#222222','#008b8b'];
   result.series.forEach((s,i)=>config.styles[seriesId(s)]={color:colors[i%colors.length],symbol:['circle','square','triangle','diamond'][ids.indexOf(s.perspective_id)%4],visible:true});
   $('#group-chart').innerHTML=`<h2>Confronto temporale della conversazione</h2><p>Offset delle sorgenti applicati. Verifica la sincronizzazione degli orologi; nessuna somma automatica tra app e gateway.</p>${result.coverage.map(c=>`<p>${esc(c.side)} · ${esc(c.device)} · metriche mancanti: ${esc(c.missing.join(', ')||'nessuna')}</p>`).join('')}<button id="diag-reset">Ripristina zoom</button> <button id="group-export">Esporta analisi JSON</button><div id="diag-legend" class="diagnostic-legend"></div><canvas id="diag-canvas" role="img" aria-label="Metriche temporali delle osservazioni della conversazione"></canvas><div id="diag-tooltip" class="diagnostic-tooltip"></div>${incidentTable(result)}`;
   $('#group-export').onclick=()=>downloadAnalysis(result,{conversation:g.key,observations:requests,start,end,...config});
   drawDiagnostics(result,config,Object.fromEntries(catalog.map(c=>[c.name,c.title])),()=>{});
  });
 }
}
