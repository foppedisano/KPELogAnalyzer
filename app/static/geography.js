"use strict";
let geographyBase;
async function openGeoTemporal(page, cell, params, valid) {
  $('#geo-temporal',page)?.remove();
  const dialog=document.createElement('dialog');dialog.id='geo-temporal';dialog.className='geo-temporal';
  dialog.innerHTML=`<header><div><span class="eyebrow">PROFILO TEMPORALE · ${esc(params.cell)} m</span><h2>Quando cambia questa zona?</h2></div><button id="gt-close" aria-label="Chiudi profilo temporale">×</button></header>
    <p>Stessi confini della cella selezionata. Andamento storico e ricorrenze descrittive; nessuna previsione o modifica automatica dell’app.</p>
    <div class="geo-date-controls"><label>Metrica<select id="gt-metric"><option value="mos">MOS a profilo fisso</option><option value="loss">Perdita riportata</option></select></label>
    <label>Orologio<select id="gt-clock"><option value="legacy_observed">Log tradizionali · ora scritta, fuso ignoto</option><option value="utc">Telemetria · UTC</option></select></label>
    <label>Storico per<select id="gt-grain"><option value="day">Giorno</option><option value="week">Settimana (lunedì)</option><option value="month">Mese</option><option value="year">Anno</option></select></label>
    <label>Da<input id="gt-start" type="datetime-local" step="1"></label><label>A (esclusa)<input id="gt-end" type="datetime-local" step="1"></label><button id="gt-apply">Applica periodo</button>
    </div><p id="gt-filters" class="muted"></p><p>UTC non è l’ora locale della zona. I log senza fuso non possono dimostrare una ricorrenza nell’ora civile locale. Il filtro direzione vale per RTP/RTCP; i dati VD descrivono il device locale.</p>
    <p id="gt-status" role="status">Caricamento…</p><div id="gt-result"></div>`;
  page.append(dialog);dialog.showModal();$('#gt-close',dialog).onclick=()=>dialog.close();
  let seq=0,last=null,offset=0,series='';
  const live=()=>valid()&&dialog.isConnected&&dialog.open;
  const el=id=>$('#gt-'+id,dialog);
  el('start').value=(params.start||'').slice(0,19);el('end').value=(params.end||'').slice(0,19);
  el('filters').textContent=`Cella ${cell.id} · ${params.direction} · posizioni ${params.quality} · piattaforma ${params.platform||'all'} · accesso ${params.access||'all'} · a monte ${params.upstream||'all'} · operatore ${params.operator||'all'}. I filtri rete si modificano nella mappa.`;
  const val=row=>last.metric.aggregation==='counter_delta'?row.rate_per_second:row.day_balanced_mean;
  const fmt=v=>v==null?'—':number(v);
  function table(items,label) {
    return `<div class="gt-scroll"><table><thead><tr><th>${label}</th><th>Media osservata</th><th>Media dei giorni</th><th>Delta totale</th><th>Delta/s osservato</th><th>Secondi osservati</th><th>Giorni / chiamate / sorgenti</th></tr></thead><tbody>${items.map(r=>`<tr><td>${esc(r.key)}</td><td>${fmt(r.mean)}</td><td>${fmt(r.day_balanced_mean)}</td><td>${fmt(r.total_delta)}</td><td>${fmt(r.rate_per_second)}</td><td>${fmt(r.observed_seconds)}</td><td>${r.days} / ${r.calls} / ${r.sources}${r.limited?' · limitata':''}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function exportFile(filename,text,type) {
    const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function draw() {
    const d=last,s=d.summary;const weekdays=['Lun','Mar','Mer','Gio','Ven','Sab','Dom'];
    const values=d.profiles.week_hour.map(val).filter(v=>v!=null),lo=Math.min(...values),hi=Math.max(...values);
    const unit=d.metric.unit+(d.metric.aggregation==='counter_delta'?'/s':'');
    const heat=d.profiles.week_hour.map(r=>{
      const value=val(r),alpha=value==null?0:.2+.65*(hi===lo?.5:(value-lo)/(hi-lo));
      return `<span class="gt-heat-cell ${r.limited?'limited':''}" style="background:rgba(30,112,155,${alpha})" title="${esc(weekdays[Math.floor(r.key/24)])} ${r.key%24}:00 · ${fmt(value)} ${esc(unit)} · ${r.days} giorni · ${r.calls} chiamate · ${r.sources} sorgenti">${value==null?'·':fmt(value)}</span>`;
    });
    const history=d.profiles.history.filter(r=>val(r)!=null), hv=history.map(val), ymin=Math.min(...hv),ymax=Math.max(...hv);
    const timeKey=k=>Date.parse(k.length===4?k+'-01-01T00:00:00Z':k.length===7?k+'-01T00:00:00Z':k+'T00:00:00Z');
    const xmin=history.length?timeKey(history[0].key):0,xmax=history.length?timeKey(history[history.length-1].key):0;
    const trend=history.length?`<svg class="gt-trend" viewBox="0 0 1000 190" role="img" aria-label="Andamento storico, punti dei periodi osservati senza interpolazione"><path d="M55 10 V155 H980" fill="none" stroke="#9ab0ba"/><text x="0" y="18">${fmt(ymax)}</text><text x="0" y="150">${fmt(ymin)}</text>${history.map(r=>`<circle cx="${55+925*(xmax===xmin?.5:(timeKey(r.key)-xmin)/(xmax-xmin))}" cy="${145-125*(ymax===ymin?.5:(val(r)-ymin)/(ymax-ymin))}" r="4" fill="#1e709b"><title>${esc(r.key)}: ${fmt(val(r))} ${esc(unit)} · ${r.days} giorni · ${r.calls} chiamate</title></circle>`).join('')}<text x="55" y="180">${esc(history[0].key)}</text><text x="980" y="180" text-anchor="end">${esc(history[history.length-1].key)}</text></svg>`:'<p>Nessun periodo osservato.</p>';
    el('result').innerHTML=`<label>Serie / contesto<select id="gt-series"><option value="">${d.selection_required?'Seleziona una serie: contesti distinti':'Serie selezionata'}</option>${(d.populations||[]).map(x=>`<option value="${esc(x.id)}" ${d.selected_series===x.id?'selected':''}>Confronto statistico di ${x.members.length} serie · ${esc(Object.entries(x.context).map(([k,v])=>k+': '+v).join(' · '))}</option>`).join('')}${d.series.map(x=>`<option value="${esc(x.id)}" ${d.selected_series===x.id?'selected':''}>${esc(Object.entries(x.context).map(([k,v])=>k+': '+v).join(' · '))}</option>`).join('')}</select></label>
      <div class="geo-stats"><div><strong>${fmt(val(s))} ${esc(unit)}</strong><small>${d.metric.aggregation==='counter_delta'?'Delta per secondo coperto':'Media con uguale peso ai giorni'}</small></div><div><strong>${s.days} giorni · ${s.calls} chiamate</strong><small>${s.sources} sorgenti · ${s.observations} osservazioni</small></div><div><strong>${fmt(s.observed_seconds)} s</strong><small>Tempo-osservazione, non disponibilità della rete</small></div></div>
      <p>${d.selection_required?'Scegli una serie per evitare di fondere osservatori, input o cicli diversi.':!s.observations?'Nessuna osservazione localizzabile per questa metrica e base temporale. Dato mancante, non qualità buona.':s.limited?'Copertura limitata: meno di 7 giorni, 10 chiamate o 3 sorgenti. Soglie esplorative, non confidenza statistica.':'Superate le soglie esplorative di copertura; questo non certifica una previsione.'}</p>
      <p>Accuratezza peggiore del fix: ${fmt(s.accuracy_max)} m. ${s.accuracy_max>params.cell?'È maggiore del lato della cella.':''} La media dei giorni riduce il peso delle giornate più osservate; non corregge differenze di utenti, reti o device.</p>
      <h3>Ricorrenza settimanale · ${esc(unit)}</h3><p>Intensità del blu = valore crescente, non diagnosi di qualità. Bordo tratteggiato = copertura limitata; punto = nessun dato. Passa su una casella per la copertura.</p>
      <div class="gt-heat-scroll"><div class="gt-heat"><span></span>${Array.from({length:24},(_,h)=>`<strong>${h}</strong>`).join('')}${weekdays.map((day,i)=>`<strong>${day}</strong>${heat.slice(i*24,(i+1)*24).join('')}`).join('')}</div></div>
      <h3>Andamento storico · ${esc(d.definition.grain)}</h3><p>Punti dei periodi osservati, senza interpolazione nei vuoti. Stessa misura della griglia settimanale.</p>${trend}${table(d.profiles.history,'Periodo')}
      <details><summary>Profilo giornaliero: le 24 ore</summary>${table(d.profiles.hour,'Ora')}</details>
      <details><summary>Giorni della settimana</summary>${table(d.profiles.weekday.map(r=>({...r,key:weekdays[r.key]})),'Giorno')}</details>
      <details><summary>Stagionalità: mese dell’anno</summary>${table(d.profiles.month,'Mese')}</details>
      <details><summary>Serie originali nel confronto</summary>${table((d.series_breakdown||[]).map(r=>({...r,key:Object.entries(r.context).map(([k,v])=>k+': '+v).join(' · ')})),'Serie')}</details><details><summary>Reti e popolazione osservata</summary>${table(d.network_breakdown.map(r=>({...r,key:Object.entries(r.context).map(([k,v])=>k+': '+v).join(' · ')})),'Contesto')}</details>
      <details><summary>Metodo, esclusioni ed evidenze</summary><ul>${d.rules.map(r=>`<li>${esc(r)}</li>`).join('')}</ul><p>Esclusioni nel perimetro di ricerca: ${esc(JSON.stringify(d.exclusions))}</p><p>Snapshot ${esc(d.snapshot)} · evidenze ${d.evidence_offset+1}–${Math.min(d.evidence_total,d.evidence_offset+d.evidence.length)} di ${d.evidence_total}</p>
      <div class="gt-scroll"><table><thead><tr><th>Intervallo</th><th>Valore</th><th>Metriche / posizione: evento e riga</th></tr></thead><tbody>${d.evidence.map(r=>`<tr><td>${esc(r.start)} → ${esc(r.end)}</td><td>${fmt(r.value)}</td><td>${r.references.map(x=>`metrica ${x.metric_id}, file ${x.file_id ?? "—"}:${x.line_no}, evento ${x.event_id} · posizione ${x.position_id}, evento ${x.position_event_id}:${x.position_line}`).join('<br>')}${r.references_truncated?' · riferimenti troncati':''}</td></tr>`).join('')}</tbody></table></div><button id="gt-prev" ${offset===0?'disabled':''}>Evidenze precedenti</button><button id="gt-next" ${!d.evidence_more?'disabled':''}>Evidenze successive</button></details>
      <p><button id="gt-json">Esporta profilo JSON</button> <button id="gt-csv">Esporta aggregati CSV</button></p><p class="muted">Il JSON include la pagina di evidenze visualizzata e indica le altre pagine. CSV: tutte le aggregazioni del profilo corrente. Coordinate e riferimenti sono dati locali da condividere consapevolmente.</p>`;
    el('series').onchange=()=>{series=el('series').value;offset=0;load();};
    el('prev').onclick=()=>{offset=Math.max(0,offset-50);load();};el('next').onclick=()=>{offset+=50;load();};
    el('json').onclick=()=>exportFile('kpe-zona-temporale.json',JSON.stringify(d,null,2),'application/json');
    el('csv').onclick=()=>{
      const fields=['profile','key','mean','day_balanced_mean','total_delta','rate_per_second','observed_seconds','observations','days','calls','sources','limited'];
      const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
      const body=Object.entries(d.profiles).flatMap(([profile,rs])=>rs.map(r=>fields.map(k=>quote(k==='profile'?profile:r[k])).concat(quote(d.version),quote(d.snapshot),quote(JSON.stringify(d.definition))).join(',')));
      exportFile('kpe-zona-temporale.csv',[fields.concat('version','snapshot','definition').join(','),...body].join('\r\n'),'text/csv;charset=utf-8');
    };
  }
  async function load(){
    const token=++seq;el('status').textContent='Calcolo del profilo…';el('result').innerHTML='';
    try {
      const definition={...params,cell:Number(params.cell),cell_id:cell.id,metric:el('metric').value,time_basis:el('clock').value,grain:el('grain').value,start:el('start').value,end:el('end').value,series_id:series,evidence_offset:offset,evidence_limit:50};
      const d=await api('analytics/geo-temporal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(definition)});
      if(!live()||token!==seq)return;last=d;draw();el('status').textContent=`${d.metric.title} · ${d.time_basis} · ${d.version}`;
    }catch(e){if(live()&&token===seq)el('status').textContent=e.message;}
  }
  for(const id of ['metric','clock','grain'])el(id).onchange=()=>{series='';offset=0;load();};
  el('apply').onclick=()=>{series='';offset=0;load();};
  try {
    const catalog=await api('analytics/catalog');if(!live())return;
    el('metric').innerHTML=catalog.geo_temporal.metrics.map(m=>`<option value="${esc(m.name)}">${esc(m.title)} · ${esc(m.unit)}</option>`).join('');
    await load();
  }catch(e){if(live())el('status').textContent=e.message;}
}
async function renderGeography(page, renderId, callId=null) {
  const callMode=callId!==null;
  page.innerHTML = (callMode?'<h2>Percorso e qualità</h2><p>Posizioni della chiamata, separate per dispositivo / sorgente.</p>':title('OSSERVATORIO GEOGRAFICO','La qualità, sul territorio.','Esplora gli indicatori di qualità audio e la loro copertura geografica. Cambia scala e periodo senza perdere lo storico.')) + `
  <section class="geo-controls panel">
    <label>Metrica<select id="geo-metric"><option value="perceptual">Perceptual Quality · AWT · 0–100</option><option value="mos">MOS · perdita RTCP · 1–5</option></select></label>
    <label>Direzione<select id="geo-direction"><option value="downstream">↓ Downstream · verso l’app</option><option value="upstream">↑ Upstream · report del peer</option></select></label>
    <label>Dimensione cella<select id="geo-cell"><option value="50">50 m</option><option value="100">100 m</option><option value="250" selected>250 m</option><option value="500">500 m</option><option value="1000">1 km</option><option value="5000">5 km</option><option value="10000">10 km</option></select></label>
    <label>Posizioni<select id="geo-quality"><option value="fresh">Nuovi aggiornamenti locali</option><option value="declared" selected>Includi posizioni SIP e aggiornamenti iOS</option></select></label>
    <details class="geo-advanced"><summary>Rete, operatore e piattaforma</summary><div class="geo-date-controls">
    <label>Piattaforma<select id="geo-platform"><option value="all">Tutte</option><option value="android">Android</option><option value="ios">iOS</option><option value="desktop">Desktop</option><option value="unknown">Sconosciuta</option></select></label>
    <label>Accesso locale<select id="geo-access"><option value="all">Tutti</option><option value="cellular">Rete mobile</option><option value="wifi">Wi-Fi</option><option value="ethernet">Ethernet</option><option value="unknown">Sconosciuto</option></select></label>
    <label>Connessione a monte<select id="geo-upstream"><option value="all">Tutte</option><option value="mobile_direct">Solo mobile diretta</option><option value="tethering">Tethering dichiarato</option><option value="onboard_wifi">Wi-Fi di bordo dichiarato</option><option value="unknown">Sconosciuta</option></select></label>
    <label>Operatore dati<select id="geo-operator"><option value="all">Tutti</option><option value="unknown">Sconosciuto</option></select></label>
    </div><p class="muted">Mobile diretta esclude Wi-Fi, tethering e accessi sconosciuti. Il tipo di dispositivo non identifica la connessione a monte.</p></details>
    <details class="geo-advanced"><summary>Periodo e date personalizzate</summary><div class="geo-date-controls"><label>Periodo<select id="geo-period"><option value="all">Intero archivio</option><option value="30">Ultimi 30 giorni</option><option value="365">Ultimo anno</option><option value="3652">Ultimi 10 anni</option><option value="custom">Date personalizzate</option></select></label>
    <label>Da<input type="datetime-local" id="geo-start" step="1"></label><label>A (esclusa)<input type="datetime-local" id="geo-end" step="1"></label>
    <button id="geo-apply" class="primary">Applica periodo</button></div></details>
  </section>
  <section class="geo-time panel"><div><span class="eyebrow">TIME MACHINE</span><strong id="geo-time-label">Intero archivio</strong><small>La finestra termina alla data scelta. Telemetria in UTC; log legacy negli orari originali.</small></div><input id="geo-time" type="range" min="0" max="1000" value="1000" aria-label="Data finale della finestra temporale"><button id="geo-prev" aria-label="Periodo precedente">←</button><button id="geo-next" aria-label="Periodo successivo">→</button></section>
  <div id="geo-stats" class="geo-stats"></div><p id="geo-context" class="geo-method"></p><p id="geo-status" role="status">Preparazione dell’archivio geografico…</p>
  <div class="geo-layout"><section class="geo-map panel"><canvas id="geo-canvas" tabindex="0" aria-label="Mappa qualità. Trascina per spostare; rotella o tasti più e meno per zoom; frecce per spostare."></canvas>
    <div class="geo-map-actions"><button id="geo-plus" aria-label="Ingrandisci mappa">+</button><button id="geo-minus" aria-label="Riduci mappa">−</button><button id="geo-fit">Inquadra dati</button><button id="geo-fullscreen" aria-label="Mappa a schermo intero">⛶</button></div>
    <div class="geo-map-settings"><label><input id="geo-routes" type="checkbox" checked> ${callMode?"Percorsi e punti interpolati":"Mostra zone stimate"}</label><label><input id="geo-locations" type="checkbox" checked> Posizioni senza valore</label><label><input id="geo-online" type="checkbox"> Strade online OSM</label><small>OSM riceve solo l’area visualizzata, mai log o valori di qualità.</small></div>
    <div id="geo-popup" class="geo-popup" hidden><button id="geo-popup-close" aria-label="Chiudi dettaglio cella">×</button><div id="geo-popup-content"></div></div><div class="geo-legend"><span><i class="geo-red"></i> &lt;3</span><span><i class="geo-amber"></i> 3–4</span><span><i class="geo-green"></i> ≥4</span><span><i class="geo-grey"></i> Senza MOS</span><small>Tratteggio: &lt;60 s o un solo giorno</small></div>
    <div class="geo-map-footer"><span id="geo-scale"></span><span>Base offline: <a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener">Natural Earth</a><span id="geo-osm-credit" hidden> · © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a></span></span></div>
  </section><aside class="geo-side"><section id="geo-detail" class="panel geo-detail"><span class="eyebrow">ESPLORA UNA ZONA</span><h2>Ogni colore ha una storia.</h2><p>Seleziona una cella per vedere qualità e copertura. Il grigio indica una posizione senza un valore associabile.</p></section><section class="panel geo-ranking"><h2>Zone da osservare</h2><p>Media MOS crescente nel periodo selezionato.</p><div id="geo-ranking"></div></section></aside></div>
  <p id="geo-method-note" class="geo-method">MOS a profilo fisso, sola perdita RTP/RTCP. Media pesata sui secondi osservati; nessuna interpolazione del percorso. Log legacy: posizioni mantenute al massimo 120 s dal messaggio. Telemetria strutturata: massimo 30 s dal fix, senza usare fix futuri o cached. Le coordinate SIP sono dichiarazioni, non nuovi fix. Celle indicative in metri; ingrandire una cella non migliora l’accuratezza della posizione. Nessun nome, ZIP o identificativo di chiamata sulla mappa.</p>`;
  if(callMode){
    $('#geo-cell',page).value='50';
    for(const selector of ['#geo-metric','#geo-direction','#geo-quality'])$(selector,page).closest('label').hidden=true;
    $$('.geo-advanced,.geo-time',page).forEach(e=>e.hidden=true);
    $('.geo-controls',page).insertAdjacentHTML('afterbegin','<label>Device / sorgente<select id="route-source" aria-label="Device del percorso"></select></label>');
    $('.geo-controls',page).insertAdjacentHTML('beforeend','<label>Posizione registrata<select id="route-point" aria-label="Posizione del percorso"><option value="">Seleziona un punto…</option></select></label>');
    $('.geo-ranking',page).hidden=true;
  }
  $('.geo-map-settings',page).insertAdjacentHTML('afterbegin','<label class="switch-key"><input id="geo-switches" type="checkbox" checked> ◆ Switch Network</label>');
  $('.geo-side',page).insertAdjacentHTML('beforeend','<section class="panel"><h2 class="switch-key">⇄ Switch Network</h2><div id="geo-switch-list">Caricamento eventi espliciti…</div></section>');
  const canvas=$('#geo-canvas',page),ctx=canvas.getContext('2d');
  let switches=[];
  let data=null, selected=null, dead=false, request=0, zoom=6, center=[.534,.37], width=900,height=620, hit=[], timer, frame, dragging=null, moved=false, appliedParams={};
  const tiles=new Map();let tileFailed=false;
  const valid=()=>!dead && renderId===renderToken && page.isConnected;
  const isPQ=()=>$('#geo-metric',page).value==='perceptual';
  const metricLabel=()=>isPQ()?'Perceptual Quality':'MOS';
  const color=v=>isPQ()?`hsl(${Math.max(0,Math.min(100,v))*1.3} 60% 40%)`:v<3?'#d84c48':v<4?'#d59a2a':'#159786';
  const project=([lon,lat])=>{lat=Math.max(-85.0511,Math.min(85.0511,lat));return [(lon+180)/360,(1-Math.log(Math.tan(Math.PI/4+lat*Math.PI/360))/Math.PI)/2];};
  const scale=()=>256*2**zoom;
  const screen=p=>[(p[0]-center[0])*scale()+width/2,(p[1]-center[1])*scale()+height/2];
  const world=p=>[(p[0]-width/2)/scale()+center[0],(p[1]-height/2)/scale()+center[1]];
  function redraw(){if(!frame && !dead)frame=requestAnimationFrame(()=>{frame=null;draw();});}
  function resize(){const r=canvas.getBoundingClientRect();width=r.width;height=r.height;const d=window.devicePixelRatio||1;canvas.width=width*d;canvas.height=height*d;ctx.setTransform(d,0,0,d,0,0);redraw();}
  function draw() {
    if(dead)return;
    ctx.fillStyle='#e5eff1';ctx.fillRect(0,0,width,height);hit=[];
    if(geographyBase){
      ctx.fillStyle='#f5f5ed';ctx.strokeStyle='#c3d2d0';ctx.lineWidth=.7;
      for(const country of geographyBase.countries){
        ctx.beginPath();
        const polygons=country.geometry.type==='Polygon'?[country.geometry.coordinates]:country.geometry.coordinates;
        for(const polygon of polygons)for(const ring of polygon){ring.forEach((p,i)=>{const [x,y]=screen(project(p));if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});ctx.closePath();}
        ctx.fill('evenodd');ctx.stroke();
      }
    }
    if($('#geo-online',page).checked)drawTiles();
    if(geographyBase && !$('#geo-online',page).checked){
      ctx.fillStyle='#506b74';ctx.font='12px system-ui';let occupied=[];
      for(const city of geographyBase.cities){
        if(zoom<6 && city.population<1000000 || zoom<8 && city.population<300000)continue;
        const [x,y]=screen(project(city.coordinates));if(x<0||x>width||y<0||y>height)continue;
        if(occupied.some(p=>Math.abs(p[0]-x)<80&&Math.abs(p[1]-y)<20))continue;
        occupied.push([x,y]);ctx.beginPath();ctx.arc(x,y,2,0,Math.PI*2);ctx.fill();ctx.fillText(city.name,x+5,y-5);
      }
    }
    if(data){
      const visibleCells=data.cells.filter(c=>callMode||c.origin!=='estimated'||$('#geo-routes',page).checked);
      const keys=new Set(visibleCells.map(c=>c.id));
      if($('#geo-locations',page).checked)for(const c of data.locations)if(!keys.has(c.id))drawCell(c,true);
      for(const c of visibleCells)drawCell(c,false);
      if(callMode&&$('#geo-routes',page).checked)drawRoute();
      if($('#geo-switches',page).checked)for(const s of switches){if(!s.location)continue;const [x,y]=screen(project([s.location.longitude,s.location.latitude]));if(x<0||y<0||x>width||y>height)continue;
        ctx.save();ctx.fillStyle=switchColor;ctx.strokeStyle='white';ctx.lineWidth=2;ctx.setLineDash(s.location.basis==='interpolated'?[2,2]:[]);ctx.beginPath();ctx.moveTo(x,y-10);ctx.lineTo(x+10,y);ctx.lineTo(x,y+10);ctx.lineTo(x-10,y);ctx.closePath();ctx.fill();ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='white';ctx.font='bold 13px system-ui';ctx.textAlign='center';ctx.fillText('⇄',x,y+4);ctx.restore();hit.push({switchEvent:s,x:x-12,y:y-12,w:24,h:24});}
    }
    const lat=Math.atan(Math.sinh(Math.PI*(1-2*center[1])))*180/Math.PI;
    const metresPerPixel=40075016.686*Math.cos(lat*Math.PI/180)/scale();
    const target=metresPerPixel*100,unit=10**Math.floor(Math.log10(target));const bar=Math.floor(target/unit)*unit;
    ctx.strokeStyle='#294954';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(20,height-44);ctx.lineTo(20+bar/metresPerPixel,height-44);ctx.stroke();
    $('#geo-scale',page).textContent=`${bar>=1000?number(bar/1000)+' km':number(bar)+' m'} · zoom ${number(zoom)}`;
  }
  function showSwitch(s){const g=s.location;const html=switchDetails(s)+`<p>${g?g.basis==='observed'?'Posizione locale registrata allo stesso istante.':'Posizione stimata fra due osservazioni entro '+g.gap_seconds+' s; non è un fix al momento dello switch.':esc(s.location_reason||'Posizione non disponibile')}</p>`+(g?g.evidence.map(e=>`<p>Posizione: ${esc(e.filename)}:${e.line} · evento #${e.event_id} · ${esc(e.ts)} · ${esc(e.kind)}</p>`).join(''):'');$('#geo-detail',page).innerHTML=html;$('#geo-popup-content',page).innerHTML=html;$('#geo-popup',page).hidden=false;redraw();}
  function switchEntries(){
    $('#geo-switch-list',page).innerHTML=`<p>${switches.length} richieste esplicite · ${switches.filter(s=>!s.location).length} senza posizione. Viola: evento, non qualità o stato della rete. Rombo tratteggiato: posizione stimata.</p>`+switches.map((s,i)=>`<button class="geo-switch-entry" data-switch="${i}">${esc(s.ts)}<br><strong>${esc(s.label)}</strong><br>${s.location?s.location.basis==='observed'?'Posizione registrata':'Posizione stimata':'Non localizzato'}</button>`).join('');
    $$('.geo-switch-entry',page).forEach(b=>b.onclick=()=>{const s=switches[+b.dataset.switch];if(s.location){center=project([s.location.longitude,s.location.latitude]);zoom=Math.max(zoom,15);}showSwitch(s);});
  }
  function drawRoute(){
    const fresh=data.points.filter(p=>p.segment!==null);
    ctx.strokeStyle='#173f68';ctx.lineWidth=2;ctx.setLineDash([5,4]);
    const byId=new Map(fresh.map(p=>[p.id,p]));
    for(const link of data.interpolation.links){
      const a=byId.get(link.start_id),b=byId.get(link.end_id);if(!a||!b)continue;
      const [x,y]=screen(project([a.longitude,a.latitude])),[u,v]=screen(project([b.longitude,b.latitude]));
      ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(u,v);ctx.stroke();
      if(Math.hypot(u-x,v-y)>35){const angle=Math.atan2(v-y,u-x),mx=(x+u)/2,my=(y+v)/2;ctx.setLineDash([]);ctx.beginPath();ctx.moveTo(mx-8*Math.cos(angle-.5),my-8*Math.sin(angle-.5));ctx.lineTo(mx,my);ctx.lineTo(mx-8*Math.cos(angle+.5),my-8*Math.sin(angle+.5));ctx.stroke();ctx.setLineDash([5,4]);}
    }
    ctx.setLineDash([]);
    for(const p of [...data.interpolation.points,...data.points]){
      const [x,y]=screen(project([p.longitude,p.latitude]));if(x<0||y<0||x>width||y>height)continue;
      ctx.beginPath();ctx.arc(x,y,p.kind==='interpolated'?3:p.segment===null?4:5,0,2*Math.PI);
      ctx.fillStyle=p.segment===null?'#fff':p.value===null?'#738b99':color(p.value);ctx.fill();ctx.strokeStyle=p.kind==='interpolated'?'#fff':'#173f68';ctx.lineWidth=1.5;ctx.stroke();
      hit.push({point:p,x:x-7,y:y-7,w:14,h:14});
    }
    for(const [p,label] of [[fresh[0],'Inizio'],[fresh.at(-1),'Fine']])if(p){const [x,y]=screen(project([p.longitude,p.latitude]));ctx.font='bold 13px system-ui';ctx.fillStyle='#173f68';ctx.fillText(label,x+9,y+(label==='Inizio'?-10:20));}
  }
  function showPoint(p){
    if(callMode)$('#route-point',page).value=String(p.id);
    if(p.kind==='interpolated'){
      const html=`<h3>${esc(p.window_ts)} · posizione interpolata</h3><p><strong>${p.value===null?'Senza valore':number(p.value)+' / 100 · Perceptual Quality'}</strong></p><p>${p.reason?esc(p.reason):`${number(p.underrun_ms)} ms di underrun su ${number(p.observed_ms)} ms osservati.`}</p><p>Posizione stimata al centro del secondo, in linea retta a velocità costante: ${p.latitude.toFixed(6)}, ${p.longitude.toFixed(6)}. La qualità usa gli eventi AWT del secondo, non i valori agli estremi. 100 indica assenza di underrun registrati, assumendo completo il log.</p>${p.position_evidence.map(e=>`<p>Estremo ${esc(e.ts)} (${esc(e.kind)}): ${esc(e.filename)}:${e.line} · evento #${e.event_id}</p>`).join('')}${p.audio_evidence.map(e=>`<p>Qualità: ${esc(e.filename)}:${esc(e.line)} · evento #${e.event_id}</p>`).join('')}`;
      $('#geo-detail',page).innerHTML=html;$('#geo-popup-content',page).innerHTML=html;$('#geo-popup',page).hidden=false;redraw();return;
    }
    const e=p.evidence;
    const html=`<h3>${esc(p.ts)}</h3><p><strong>${p.value===null?'Senza valore':number(p.value)+' / 100 · Perceptual Quality'}</strong></p><p>${p.reason?esc(p.reason):`${number(p.underrun_ms)} ms in underrun su ${number(p.observed_ms)} ms di chiamata nella finestra.`}</p><p>${p.kind==='cached'?'Coordinate dalla cache':p.kind==='sip_local'?'Coordinate dichiarate nel messaggio SIP; età reale ignota':p.kind==='sip_config'?'Aggiornamento locale degli header SIP; età del fix non verificata':'Aggiornamento locale'} · ${p.latitude.toFixed(6)}, ${p.longitude.toFixed(6)}</p><p>Posizione: ${esc(e.filename)}:${e.line} · evento #${e.event_id}</p>${p.audio_evidence.map(e=>`<p>Qualità: ${esc(e.filename)}:${esc(e.line)} · evento #${e.event_id}</p>`).join('')}`;
    $('#geo-detail',page).innerHTML=html;$('#geo-popup-content',page).innerHTML=html;$('#geo-popup',page).hidden=false;redraw();
  }
  function drawCell(c,grey){
    const [w,s,e,n]=c.bounds,[x,y]=screen(project([w,n])),[right,bottom]=screen(project([e,s]));
    if(right<-10||x>width+10||bottom<-10||y>height+10)return;
    const cw=Math.max(2,right-x),ch=Math.max(2,bottom-y),cx=(x+right)/2,cy=(y+bottom)/2,small=cw<9;
    ctx.fillStyle=grey?'#738b99':color(c.mean);ctx.strokeStyle=selected?.id===c.id?'#132f3b':grey?'#fff':color(c.mean);ctx.lineWidth=selected?.id===c.id?3:1.5;ctx.globalAlpha=grey?.35:c.origin==='estimated'?.24:.78;
    ctx.beginPath();if(small)ctx.arc(cx,cy,grey?3.5:6,0,2*Math.PI);else ctx.rect(x,y,cw,ch);ctx.fill();ctx.globalAlpha=1;
    ctx.setLineDash(!grey&&(c.origin==='estimated'||(!c.origin&&c.limited))?[4,4]:[]);ctx.stroke();ctx.setLineDash([]);
    if(!grey&&c.origin==='estimated'&&!small){
      ctx.save();ctx.beginPath();ctx.rect(x,y,cw,ch);ctx.clip();ctx.globalAlpha=.22;ctx.lineWidth=1;
      for(let d=-ch;d<cw;d+=12){ctx.beginPath();ctx.moveTo(x+d,y+ch);ctx.lineTo(x+d+ch,y);ctx.stroke();}ctx.restore();
    }
    if(!grey&&cw>55&&ch>30){ctx.fillStyle='#102e35';ctx.font='bold 14px system-ui';ctx.fillText(number(c.mean),x+5,y+19);}
    hit.push({c,grey,x:small?cx-8:x,y:small?cy-8:y,w:small?16:cw,h:small?16:ch});
  }
  function drawTiles(){
    const z=Math.floor(zoom),n=2**z,tl=world([0,0]),br=world([width,height]);
    for(let x=Math.max(0,Math.floor(tl[0]*n));x<=Math.min(n-1,Math.floor(br[0]*n));x++)for(let y=Math.max(0,Math.floor(tl[1]*n));y<=Math.min(n-1,Math.floor(br[1]*n));y++){
      const key=`${z}/${x}/${y}`;let img=tiles.get(key);
      if(!img){img=new Image();tiles.set(key,img);img.onload=redraw;img.onerror=()=>{tileFailed=true;$('#geo-status',page).textContent='Strade online non disponibili per alcune aree: resta visibile la base offline.';};img.src=`/api/map-tile?z=${z}&x=${x}&y=${y}`;}
      if(img.complete&&img.naturalWidth){const [px,py]=screen([x/n,y/n]),size=scale()/n;ctx.drawImage(img,px,py,size+.5,size+.5);}
    }
    if(tiles.size>250){for(const [key,img] of tiles){if(img.complete)tiles.delete(key);if(tiles.size<150)break;}}
  }
  function fit(bounds,maxZoom=16){
    if(!bounds.length)return;
    const points=bounds.flatMap(b=>[project([b[0],b[1]]),project([b[2],b[3]])]);
    const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
    center=[(minX+maxX)/2,(minY+maxY)/2];zoom=Math.max(2,Math.min(maxZoom,Math.log2(Math.min((width-100)/Math.max(.00001,maxX-minX),(height-180)/Math.max(.00001,maxY-minY))/256)));redraw();
  }
  function showQualityCell(c){
    const estimated=c.origin==='estimated';
    const proof=e=>`<li>${esc(e.ts)} · PQ ${number(e.value)}${(e.position||[]).map(p=>`<br>Posizione (${esc(p.kind)}): ${esc(p.filename)}:${esc(p.line)} · evento #${esc(p.event_id)}`).join('')}${e.position_truncated?'<br>Altre posizioni omesse':''}${(e.audio||[]).map(p=>`<br>AWT: ${esc(p.filename)}:${esc(p.line)} · evento #${esc(p.event_id)}`).join('')}</li>`;
    const coverage=x=>`<dl><dt>Secondi campionati / giorni</dt><dd>${number(x.seconds)} s / ${x.days}</dd><dt>Passaggi osservati</dt><dd>${x.passes}</dd><dt>Secondi interessati da underrun</dt><dd>${number(x.affected_seconds)} s · ${number(x.underrun_ms)} ms complessivi di underrun</dd><dt>Minimo / massimo</dt><dd>${number(x.minimum)} / ${number(x.maximum)}</dd>${x.origin==='estimated'?`<dt>Distanza temporale fra gli estremi</dt><dd>${number(x.gap_min_seconds)}–${number(x.gap_max_seconds)} s</dd>`:''}<dt>Prima / ultima osservazione</dt><dd>${esc(stamp(x.first))}<br>${esc(stamp(x.last))}</dd></dl>`;
    const evidence=x=>`<details><summary>Prove dei campioni${x.evidence_truncated?' · prime 20':''}</summary><ul>${(x.evidence||[]).map(proof).join('')}</ul></details>`;
    const html=`<span class="eyebrow">${estimated?'ZONA STIMATA':'DATO DIRETTO'} · CELLA ${number(data.cell)} m</span><div class="geo-score">${number(c.mean)}<small>Perceptual Quality · media ${estimated?'stimata nella zona':'dei campioni localizzati'}</small></div><p>${estimated?'Qui mancano dati diretti. La qualità AWT è calcolata dai log; è la posizione a essere stimata lungo il percorso.':'Il colore usa soltanto i dati associati a posizioni registrate. Eventuali stime non modificano questa media. Le posizioni SIP possono avere età reale ignota.'}</p>${coverage(c)}<p>${c.limited?'Copertura limitata: pochi secondi o un solo giorno. ':''}100 significa nessun underrun registrato, assumendo completo il log AWT.</p>${estimated?'<p>Posizione interpolata in linea retta a velocità costante, massimo 120 s fra estremi. Il tragitto reale può essere diverso.</p>':''}<p>Passaggi: sequenze nella stessa cella e sorgente; per le stime servono secondi consecutivi, per i dati diretti il divario massimo è 120 s. Non sono viaggi indipendenti verificati.</p>${evidence(c)}${c.estimate?`<details><summary>Stime disponibili · escluse dal colore</summary><p>Media stimata ${number(c.estimate.mean)}; prevale il dato diretto ${number(c.mean)}.</p>${coverage(c.estimate)}${evidence(c.estimate)}</details>`:''}`;
    $('#geo-detail',page).innerHTML=html;$('#geo-popup-content',page).innerHTML=html;
    for(const el of $$('.geo-score',page))el.style.color=color(c.mean);
    $('#geo-popup',page).hidden=false;
  }
  function show(c,grey=false){
    selected=c;const [w,s,e,n]=c.bounds;
    if(isPQ()&&!callMode&&!grey){showQualityCell(c);redraw();return;}
    $('#geo-detail',page).innerHTML=grey?`<span class="eyebrow">POSIZIONE OSSERVATA</span><h2>Nessun valore associabile</h2><p>Questa cella contiene coordinate nei log, ma nessun campione ${metricLabel()} valido con i criteri e il periodo selezionati.</p>`:
      `<span class="eyebrow">${esc(data.direction)} · CELLA ${number(data.cell)} m</span><div class="geo-score" data-color="${color(c.mean)}">${number(c.mean)}<small>${metricLabel()} · media</small></div><p>${callMode?'Campioni della sola chiamata e sorgente selezionata.':c.limited?'◌ Copertura limitata: interpreta con cautela.':'● Osservazioni su più giorni.'}</p><dl><dt>Minimo / massimo</dt><dd>${number(c.minimum)} / ${number(c.maximum)}</dd><dt>Tempo osservato</dt><dd>${number(c.seconds)} s</dd><dt>Intervalli / giorni</dt><dd>${c.observations} / ${c.days}</dd><dt>Accuratezza dichiarata peggiore</dt><dd>${c.accuracy_max==null?'Non disponibile':number(c.accuracy_max)+' m'}</dd><dt>Prima / ultima osservazione</dt><dd>${esc(stamp(c.first))}<br>${esc(stamp(c.last))}</dd></dl>`;
    const scoreEl=$('.geo-score',page);if(scoreEl)scoreEl.style.color=scoreEl.dataset.color;
    $('#geo-detail',page).innerHTML+=`<p class="muted">Centro cella: ${((s+n)/2).toFixed(5)}, ${((w+e)/2).toFixed(5)}</p>`;
    if(isPQ()&&!grey)$('#geo-detail',page).innerHTML+=`<p>${c.observations} finestre distinte campionate al timestamp delle posizioni. Le statistiche della cella usano solo queste posizioni registrate.</p><p>${c.speed_max_mps==null?'Velocità non disponibile.':`Velocità media massima fra fix: ${number(c.speed_max_mps*3.6)} km/h.`} ${c.movement_exceeds_cell?'Movimento stimato in un secondo superiore alla dimensione della cella: localizzazione indicativa.':''}</p>`;
    if(callMode){const points=data.points.filter(p=>p.cell_id===c.id);$('#geo-detail',page).innerHTML+=`<p>${points.length} messaggi di posizione in questa cella. Usa “Posizione registrata” per consultarne orario ed evidenze.</p>`;if(grey)$('#geo-detail',page).innerHTML+=`<ul>${[...new Set(points.map(p=>p.reason).filter(Boolean))].map(r=>`<li>${esc(r)}</li>`).join('')}</ul>`;}
    $('#geo-popup-content',page).innerHTML=$('#geo-detail',page).innerHTML;
    const popupScore=$('#geo-popup .geo-score',page);if(popupScore)popupScore.style.color=popupScore.dataset.color;
    $('#geo-popup',page).hidden=!isPQ();redraw();if(!isPQ())openGeoTemporal(page,c,{...appliedParams,cell:data.cell,direction:data.direction,quality:data.quality},valid);
  }
  function setZoom(value,anchor=[width/2,height/2]){const before=world(anchor);zoom=Math.max(2,Math.min(18,value));const after=world(anchor);center=[center[0]+before[0]-after[0],center[1]+before[1]-after[1]];redraw();}
  canvas.onwheel=e=>{e.preventDefault();const r=canvas.getBoundingClientRect();setZoom(zoom+(e.deltaY<0?.5:-.5),[e.clientX-r.left,e.clientY-r.top]);};
  canvas.onpointerdown=e=>{canvas.setPointerCapture(e.pointerId);dragging=[e.clientX,e.clientY,...center];moved=false;};
  canvas.onpointermove=e=>{if(!dragging)return;const dx=e.clientX-dragging[0],dy=e.clientY-dragging[1];if(Math.abs(dx)+Math.abs(dy)>4)moved=true;center=[dragging[2]-dx/scale(),Math.max(0,Math.min(1,dragging[3]-dy/scale()))];redraw();};
  canvas.onpointerup=e=>{dragging=null;if(moved)return;const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;const h=[...hit].reverse().find(h=>x>=h.x&&x<=h.x+h.w&&y>=h.y&&y<=h.y+h.h);if(h){if(h.switchEvent)showSwitch(h.switchEvent);else if(h.point)showPoint(h.point);else show(h.c,h.grey);}};
  canvas.onpointercancel=()=>{dragging=null;};canvas.ondblclick=e=>{const r=canvas.getBoundingClientRect();setZoom(zoom+1,[e.clientX-r.left,e.clientY-r.top]);};
  canvas.onkeydown=e=>{if(['+','=','-','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();if(e.key==='+'||e.key==='=')setZoom(zoom+1);else if(e.key==='-')setZoom(zoom-1);else{center[e.key==='ArrowLeft'||e.key==='ArrowRight'?0:1]+=(e.key==='ArrowLeft'||e.key==='ArrowUp'?-80:80)/scale();redraw();}}};
  $('#geo-popup-close',page).onclick=()=>{$('#geo-popup',page).hidden=true;};
  $('#geo-plus',page).onclick=()=>setZoom(zoom+1);$('#geo-minus',page).onclick=()=>setZoom(zoom-1);
  $('#geo-fit',page).onclick=()=>fit((callMode?data?.locations||[]:data?.cells.length?data.cells:data?.locations||[]).map(c=>c.bounds),callMode||data?.estimated_cells?17:12);
  $('#geo-fullscreen',page).onclick=safe(async()=>{if(document.fullscreenElement)await document.exitFullscreen();else await $('.geo-map',page).requestFullscreen();});
  $('#geo-locations',page).onchange=redraw;
  $('#geo-online',page).onchange=()=>{$('#geo-osm-credit',page).hidden=!$('#geo-online',page).checked;redraw();};
  function range(){
    if(!data?.extent[0])return;
    const lo=timeValue(data.extent[0]),hi=timeValue(data.extent[1])+1000;
    const end=lo+(hi-lo)*Number($('#geo-time',page).value)/1000;
    const period=$('#geo-period',page).value;
    if(period==='all'){$('#geo-start',page).value='';$('#geo-end',page).value='';$('#geo-time-label',page).textContent='Intero archivio';return;}
    if(period==='custom')return;
    $('#geo-end',page).value=new Date(end).toISOString().slice(0,19);
    $('#geo-start',page).value=new Date(end-Number(period)*86400000).toISOString().slice(0,19);
    $('#geo-time-label',page).textContent='Fino al '+new Date(end).toISOString().slice(0,10);
  }
  async function load(first=false){
    const token=++request;$('#geo-status',page).textContent='Calcolo delle celle nel periodo selezionato…';
    const pq=isPQ();$('#geo-routes',page).closest('label').hidden=!pq;$('#geo-direction',page).disabled=pq;if(pq)$('#geo-direction',page).value='downstream';
    const query=new URLSearchParams({metric:$('#geo-metric',page).value,cell:$('#geo-cell',page).value,direction:$('#geo-direction',page).value,quality:$('#geo-quality',page).value});
    for(const k of ['platform','access','upstream','operator'])query.set(k,$('#geo-'+k,page).value);
    for(const k of ['start','end'])if($('#geo-'+k,page).value)query.set(k,$('#geo-'+k,page).value);
    if(callMode){query.set('call',callId);if($('#route-source',page).value)query.set('perspective',$('#route-source',page).value);}
    try{
      const next=await api((callMode?'call-route?':'geography?')+query);if(!valid()||token!==request)return;data=next;appliedParams=Object.fromEntries(query);selected=null;$('#geo-popup',page).hidden=true;
      const switchQuery=Object.fromEntries([...query].filter(([k,v])=>['start','end','quality','platform','access','upstream','operator'].includes(k)&&v));
      if(callMode){switchQuery.call_id=callId;if(data.perspective_id)switchQuery.perspective_id=data.perspective_id;switchQuery.quality='declared';}
      switches=[];$('#geo-switch-list',page).textContent='Caricamento Switch Network…';
      // Quality cells are already available; the optional overlay must not delay painting.
      void api('analytics/network-switches',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(switchQuery)})
        .then(response=>{if(!valid()||token!==request)return;switches=response.events;switchEntries();redraw();})
        .catch(error=>{if(!valid()||token!==request)return;switches=[];$('#geo-switch-list',page).textContent='Switch Network non disponibili: '+error.message;});
      if(callMode){
        $('#route-source',page).innerHTML=data.sources.map(s=>`<option value="${s.id}">${esc(s.label)} · P${s.id}</option>`).join('');$('#route-source',page).value=data.perspective_id||'';
        $('#route-point',page).innerHTML='<option value="">Seleziona un punto…</option>'+data.points.map(p=>`<option value="${p.id}">${esc(p.ts)} · ${p.value===null?'senza valore':number(p.value)+' PQ'}${p.kind==='cached'?' · cache':''}</option>`).join('');
        $('#geo-stats',page).innerHTML=`<div><span>Media campioni localizzati</span><strong>${data.mean===null?'—':number(data.mean)}</strong><small>Perceptual Quality</small></div><div><span>Posizioni registrate</span><strong>${data.points.length}</strong></div><div><span>Celle con qualità</span><strong>${data.cells.length}</strong><small>${data.samples} finestre campionate</small></div>`;
        $('#geo-stats',page).innerHTML+=`<div><span>Tratto interpolato · media / minimo</span><strong>${data.interpolation.mean===null?'—':number(data.interpolation.mean)+' / '+number(data.interpolation.minimum)}</strong><small>${data.interpolation.points.length} punti · ${number(data.interpolation.evaluated_seconds)} s valutabili</small></div>`;
        $('#geo-context',page).textContent=data.end_basis==='last_call_evidence'?'Fine chiamata non registrata: copertura limitata all’ultima evidenza attribuita alla chiamata.':'';
        $('#geo-status',page).textContent=data.points.length?`${data.points.length} posizioni · celle da ${data.cell} m · percorso della sola sorgente selezionata.`:'Nessuna posizione locale attribuibile a questa chiamata e sorgente.';
        $('.geo-legend',page).innerHTML='<span>Perceptual Quality: 0 → 100 · rosso → verde</span><span>Grigio: consulta il motivo</span><span>○ Cache · punti piccoli: posizione interpolata · linea: percorso stimato</span>';
        $('#geo-method-note',page).textContent='Qualità = 100 − percentuale di tempo in underrun AWT. 100 significa nessun underrun registrato, assumendo completo il log; non è qualità percettiva verificata. Punti piccoli: posizione stimata al centro di ogni secondo completo fra due messaggi, in linea retta e a velocità costante, con qualità AWT di quel secondo. Interruzione oltre 120 s; niente adattamento a strade o ferrovie. Le dichiarazioni SIP possono avere coordinate datate. Media e minimo del tratto usano i secondi valutabili; le celle e la media localizzata usano solo posizioni registrate. Cache e secondi ambigui non forniscono qualità interpolata.';
        $('#geo-detail',page).innerHTML='<h3>Esplora il percorso</h3><p>Seleziona un punto o un quadrato per vedere qualità ed evidenze. Il selettore “Posizione registrata” permette di distinguere passaggi ripetuti nello stesso luogo.</p>';
        if(first)fit(data.locations.map(c=>c.bounds),17);redraw();return;
      }
      $('#geo-stats',page).innerHTML=`<div><span>${pq?"Media dei dati diretti":"Media nel periodo"}</span><strong>${data.mean==null?'—':number(data.mean)}</strong><small>${metricLabel()} · ${pq?'media dei secondi campionati':'pesata sul tempo'}</small></div><div><span>Zone con ${metricLabel()}</span><strong>${data.cells.length}</strong><small>${pq?data.direct_cells+" dirette · "+data.estimated_cells+" stimate · ":""}celle da ${number(data.cell)} m</small></div><div><span>${pq?'Secondi campionati':'Tempo localizzato'}</span><strong>${number(pq?data.seconds:data.seconds/60)} <small>${pq?'s':'min'}</small></strong><small>somma degli intervalli deduplicati</small></div><div><span>Archivio posizioni</span><strong>${data.extent[2]}</strong><small>evidenze conservate, anche ripetute</small></div>`;
      const operators=$('#geo-operator',page),operatorValue=operators.value;
      operators.innerHTML='<option value="all">Tutti</option><option value="unknown">Sconosciuto</option>'+data.mobility.operators.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');operators.value=operatorValue;
      $('#geo-context',page).textContent=`Accesso noto: ${data.network_known_percent==null?'—':number(data.network_known_percent)+'%'} del tempo ${metricLabel()} selezionato. Archivio movimento: ${data.mobility.samples} campioni in ${data.mobility.sequences} sequenze locali; ${data.mobility.network_observations} osservazioni di rete. Nessuna previsione attiva. Stato di rete utilizzabile per massimo ${data.mobility.network_max_age_seconds} s.`;
      $('#geo-status',page).textContent=data.cells.length?`${data.cells.length} zone · ${data.quality==='fresh'?'nuovi aggiornamenti locali':'incluse posizioni SIP dichiarate, età reale ignota'} · celle tratteggiate con copertura limitata.`:`Nessun ${metricLabel()} localizzabile con questi filtri. I punti grigi indicano solo posizioni note.`;
      if(pq)$('#geo-status',page).textContent=`${data.direct_cells} zone con dati diretti · ${data.estimated_cells} zone stimate. Il dato diretto ha precedenza. Clic su una zona per origine, disturbi e copertura.`;
      data.cells.sort((a,b)=>a.mean-b.mean);
      $('.geo-ranking p',page).textContent=pq?'Media crescente; origine diretta o stimata indicata per ogni zona.':`Media ${metricLabel()} crescente nel periodo selezionato.`;
      $('.geo-legend',page).innerHTML=pq?'<span>Perceptual Quality: 0 → 100 · rosso → verde</span><span><i class="geo-grey"></i> Senza valore</span><span>Pieno: dato diretto · trasparente e tratteggiato: stima</span><small>Grigio: dati insufficienti</small>':'<span><i class="geo-red"></i> &lt;3</span><span><i class="geo-amber"></i> 3–4</span><span><i class="geo-green"></i> ≥4</span><span><i class="geo-grey"></i> Senza MOS</span>';
      $('#geo-method-note',page).textContent=pq?'Perceptual Quality = 100 − percentuale di tempo in underrun AWT. Finestre di 1 s, ritagliate e normalizzate sulla porzione attiva ai confini della chiamata; inizio/fine osservati, durata dichiarata come fallback. Durante la chiamata, assenza di underrun registrati = 100, anche senza heartbeat o contatori AWT; un episodio aperto resta attivo fino alla fine della chiamata o alla ricreazione del device. Le celle usano il secondo che contiene la posizione. Le celle stimate riempiono solo zone senza dati diretti attraversate da percorsi della stessa chiamata/sorgente: posizione interpolata in linea retta, qualità AWT del secondo, gap massimo 120 s. Nessun adattamento a strade o ferrovie né estensione alle zone vicine. Il dato diretto ha precedenza; le stime presenti nella stessa cella restano separate nel dettaglio. La media descrive i secondi campionati, non tutta la permanenza nella cella. Le posizioni SIP hanno età reale ignota. Indicatore operativo, non MOS percettivo validato.':'MOS a profilo fisso dalla sola perdita RTCP. Media pesata sul tempo. Posizioni legacy mantenute al massimo 120 s; coordinate SIP dichiarate con età reale ignota.';
      $('#geo-ranking',page).innerHTML=data.cells.slice(0,12).map((c,i)=>`<button class="geo-zone" data-zone="${i}"><span class="geo-zone-dot" data-color="${color(c.mean)}"></span><span>Zona ${i+1}<small>${c.origin==='estimated'?'Stima · ':c.origin==='direct'?'Diretto · ':''}${number(c.seconds)} s · ${c.days} giorni</small></span><strong>${number(c.mean)}</strong></button>`).join('')||'<p class="muted">Nessuna zona valutabile.</p>';
      $$('.geo-zone-dot',page).forEach(e=>e.style.background=e.dataset.color);
      $$('.geo-zone',page).forEach(b=>b.onclick=()=>{const c=data.cells[+b.dataset.zone];fit([c.bounds]);show(c);});
      $('#geo-detail',page).innerHTML='<span class="eyebrow">ESPLORA UNA ZONA</span><h2>Seleziona una cella.</h2><p>La media considera solo i campioni valutabili. I periodi senza dati restano senza valore.</p>';
      if(data.locations_truncated)$('#geo-status',page).textContent+=' Posizioni grigie limitate: restringere il periodo.';
      if(data.conflicting_intervals)$('#geo-status',page).textContent+=` ${data.conflicting_intervals} intervalli esclusi per posizioni discordanti.`;
      if(first){range();fit((data.cells.length?data.cells:data.locations).map(c=>c.bounds),data.estimated_cells?17:12);}
      redraw();
    }catch(error){if(valid()&&token===request){$('#geo-status',page).textContent=error.message;data=null;$('#geo-popup',page).hidden=true;$('#geo-detail',page).textContent='Correggere i filtri per ricalcolare la mappa.';$('#geo-stats',page).innerHTML='';$('#geo-context',page).textContent='';$('#geo-ranking',page).innerHTML='';redraw();}}
  }
  $('#geo-apply',page).onclick=()=>load();
  $('#geo-routes',page).onchange=redraw;
  $('#geo-switches',page).onchange=redraw;
  if(callMode){$('#route-source',page).onchange=()=>load(true);$('#route-point',page).onchange=()=>{const p=data?.points.find(p=>p.id===+$('#route-point',page).value);if(p){center=project([p.longitude,p.latitude]);showPoint(p);}};}
  for(const k of ['metric','cell','direction','quality','platform','access','upstream','operator'])$('#geo-'+k,page).onchange=()=>load();
  $('#geo-period',page).onchange=()=>{range();load();};
  for(const k of ['start','end'])$('#geo-'+k,page).onchange=()=>{$('#geo-period',page).value='custom';$('#geo-time-label',page).textContent='Date personalizzate';};
  $('#geo-time',page).oninput=()=>{if(['all','custom'].includes($('#geo-period',page).value))$('#geo-period',page).value='30';range();clearTimeout(timer);timer=setTimeout(()=>load(),250);};
  for(const [id,sign] of [['prev',-1],['next',1]])$('#geo-'+id,page).onclick=()=>{$('#geo-time',page).value=Math.max(0,Math.min(1000,Number($('#geo-time',page).value)+sign*50));$('#geo-time',page).oninput();};
  const observer=new ResizeObserver(resize);observer.observe(canvas);
  const previousCleanup=callMode?chartCleanup:null;
  chartCleanup=()=>{previousCleanup?.();dead=true;observer.disconnect();clearTimeout(timer);if(frame)cancelAnimationFrame(frame);for(const img of tiles.values()){img.onload=null;img.onerror=null;}};
  resize();
  try{if(!geographyBase)geographyBase=await withLoading(async () => (await fetch('/basemap.json')).json());if(valid())redraw();}catch(e){if(valid())$('#geo-status',page).textContent='Base geografica offline non disponibile.';}
  if(valid())await load(true);
}
