"use strict";

// Nice bounds, with integral steps for discrete packet counts.
function chartScale(values, unit) {
  if (unit === 'MOS' && values.every(v => v >= 1 && v <= 5)) return {low:1, high:5, ticks:[1,2,3,4,5]};
  let low = 0, high = unit === 'MOS' ? 5 : 0;
  for (const v of values) { low = Math.min(low, v); high = Math.max(high, v); }
  const raw = (high - low || 1) / 4;
  const base = 10 ** Math.floor(Math.log10(raw));
  let step = [1, 2, 5, 10].map(n => n * base).find(n => n >= raw);
  if (['packets','count','samples','bytes','chunks'].includes(unit)) step = Math.max(1, Math.ceil(step));
  low = Math.floor(low / step) * step;
  high = Math.max(low + step, Math.ceil(high / step) * step);
  const ticks = [];
  for (let i = 0; i <= Math.round((high - low) / step); i++) ticks.push(Number((low + i * step).toPrecision(12)));
  return {low, high, ticks};
}

async function mountMultiChart(root, ids, initialMetric) {
  const options = await api('metric-options?calls=' + ids.join(','));
  if (!root.isConnected) return;
  const selected = new Map(), cache = new Map(), hidden = new Set();
  let points = [], generation = 0, disposed = false, zoom = null, cursor = null, bounds = null;
  const defaults = name => {
    const stats = [...new Set(state.metrics.filter(m => m.name === name).map(m => m.statistic))];
    return {stats: stats.length ? stats : ['last'], value: stats.includes('last') ? 'last' : stats[0] || 'last'};
  };
  selected.set(initialMetric, defaults(initialMetric.split('|')[0]).value);
  root.innerHTML = `<div class="panel"><div class="panel-head"><h2>Andamento delle metriche</h2></div><div class="panel-body">
    <details class="chart-picker"><summary>Aggiungi metriche</summary><label>Cerca una metrica<input type="search" class="metric-search" placeholder="MOS, jitter, pacchetti…"></label><div class="metric-choices"></div></details>
    <div class="toolbar chart-presets">Selezioni rapide: <button data-preset="quality">Qualità</button><button data-preset="network">Rete</button><button data-preset="receive">Ricezione</button><button data-preset="clear">Rimuovi tutte</button></div>
    <div class="selected-metrics"></div><div class="chart-controls"><label>Allineamento<select class="chart-axis"><option value="relative">Tempo dalla prima evidenza</option><option value="absolute">Orario log + correzione</option></select></label><label class="check"><input type="checkbox" class="chart-invalid"> Mostra anomali</label><button class="zoom-out" aria-label="Riduci zoom temporale">−</button><button class="zoom-in" aria-label="Aumenta zoom temporale">+</button><button class="reset-zoom">Mostra tutta la chiamata</button></div>
    <label class="check"><input type="checkbox" class="chart-duplicates"> Mostra copie storiche della stessa sorgente</label>
    <p class="muted">Di norma ogni sorgente compare una volta per chiamata; flussi e SSRC distinti restano separati. Una scala per unità; le metriche raw restano separate. La rotella scorre la pagina. Ctrl + rotella ingrandisce intorno al puntatore; i pulsanti − e + agiscono al centro. Lo zoom è comune a tutti i pannelli. Clic sulla legenda per nascondere una curva. RTT = andata e ritorno, non ritardo audio.</p>
    <p class="chart-status" role="status"></p><p class="chart-notes muted"></p><div class="multi-panels"></div><div class="multi-readout" aria-live="off">Passa sul grafico per leggere i campioni e le evidenze.</div><div class="metric-statistics"></div><div class="metric-episodes"></div>
    </div></div>`;
  const titleFor = value => options.find(o => o.value === value)?.title || value;
  function controls() {
    const query = $('.metric-search', root).value.toLocaleLowerCase();
    $('.metric-choices', root).innerHTML = [...new Set(options.map(o => o.group))].map(group => `<fieldset><legend>${esc(group)}</legend>${options.filter(o => o.group === group && (o.title + o.name).toLocaleLowerCase().includes(query)).map(o => `<label><input type="checkbox" value="${esc(o.value)}" ${selected.has(o.value) ? 'checked' : ''}>${esc(o.title)} <small>${esc(o.name)}</small></label>`).join('')}</fieldset>`).join('');
    $$('.metric-choices input', root).forEach(el => el.onchange = safe(async () => {
      if (el.checked) selected.set(el.value, defaults(el.value.split('|')[0]).value); else selected.delete(el.value);
      controls(); await load();
    }));
    $('.selected-metrics', root).innerHTML = [...selected].map(([value, stat], i) => {
      const stats = defaults(value.split('|')[0]).stats;
      return `<div class="metric-chip"><strong>${esc(titleFor(value))}</strong>${stats.length > 1 ? `<select data-stat="${i}" aria-label="Statistica ${esc(titleFor(value))}">${stats.map(s => `<option ${s === stat ? 'selected' : ''}>${esc(s)}</option>`).join('')}</select>` : ''}<a class="small-button" href="/api/metrics?${esc(params(value, stat).toString())}&amp;format=csv">CSV</a><button data-remove="${i}" aria-label="Rimuovi ${esc(titleFor(value))}">×</button></div>`;
    }).join('');
    $$('[data-remove]', root).forEach(b => b.onclick = safe(async () => {selected.delete([...selected.keys()][+b.dataset.remove]); controls(); await load();}));
    $$('[data-stat]', root).forEach(el => el.onchange = safe(async () => {selected.set([...selected.keys()][+el.dataset.stat], el.value); controls(); await load();}));
  }
  function params(value, stat) {
    const [name, direction = ''] = value.split('|');
    return new URLSearchParams({calls: ids.join(','), name, direction, statistic: stat, invalid: $('.chart-invalid', root).checked ? '1' : '0', duplicates: $('.chart-duplicates', root).checked ? '1' : '0'});
  }
  const seriesKey = p => JSON.stringify([p.name,p.statistic,p.call_id,p.perspective_id,p.direction,p.flow,p.ssrc,p.device,p.sample_kind,p.observer,p.output_device,p.input_device,p.lifecycle]);
  const seriesLabel = p => `${p.name} · ${p.statistic || ''} · #${p.call_id} · P${p.perspective_id} · ${p.label} · ${p.measurement_context?.label || p.direction || ''}${p.flow ? ' · flusso '+p.flow : ''}${p.ssrc ? ' · SSRC '+p.ssrc : ''}${p.device ? ' · '+p.device : ''}${p.observer ? ' · '+p.observer : ''}${p.output_device ? ' · output '+p.output_device : ''}${p.input_device ? ' · input '+p.input_device : ''}${p.lifecycle ? ' · ciclo '+p.lifecycle : ''}`;
  const xvalue = p => $('.chart-axis', root).value === 'absolute' ? timeValue(p.ts) + (p.clock_offset || 0) * 1000 : timeValue(p.ts) - timeValue(p.start);
  const end = p => p.valid_until ? xvalue(p) + timeValue(p.valid_until) - timeValue(p.ts) : xvalue(p);
  let series = [], panels = [];
  function layout() {
    const grouped = new Map();
    for (const p of points) {const key = seriesKey(p); if (!grouped.has(key)) grouped.set(key, []); grouped.get(key).push(p);}
    series = [...grouped].map(([key, ps], i) => ({key, ps: ps.sort((a,b) => timeValue(a.ts)-timeValue(b.ts)), color: colors[i % colors.length], index:i}));
    const units = new Map();
    for (const s of series) {const p = s.ps[0], key = p.unit === 'raw' ? 'raw · '+p.name : p.unit || 'unità non nota · '+p.name; if (!units.has(key)) units.set(key, []); units.get(key).push(s);}
    panels = [...units].map(([title, ss]) => ({title, ss}));
    $('.multi-panels', root).innerHTML = panels.map((panel,i) => `<section class="multi-panel"><h3>${esc(panel.title)}</h3><div class="legend">${panel.ss.map(s => `<button data-series="${s.index}" aria-pressed="${!hidden.has(s.key)}" class="${hidden.has(s.key) ? 'disabled' : ''}"><span class="series-dot">●</span>${esc(seriesLabel(s.ps[0]))}</button>`).join('')}</div><div class="chart-area"><canvas data-panel="${i}" role="img" aria-label="Grafico temporale ${esc(panel.title)}"></canvas></div></section>`).join('');
    $$('[data-series]', root).forEach(b => {
      const s = series[+b.dataset.series];
      const svg = document.createElementNS('http://www.w3.org/2000/svg','svg'); svg.setAttribute('width','12'); svg.setAttribute('height','12');
      const circle = document.createElementNS(svg.namespaceURI,'circle'); for (const [k,v] of Object.entries({cx:6,cy:6,r:5,fill:s.color})) circle.setAttribute(k,v); svg.append(circle); $('.series-dot',b).replaceWith(svg);
      b.onclick = () => {hidden.has(s.key) ? hidden.delete(s.key) : hidden.add(s.key); b.classList.toggle('disabled',hidden.has(s.key)); b.setAttribute('aria-pressed',!hidden.has(s.key)); draw(); readout(); statistics();};
    });
    $$('canvas',root).forEach(canvas => {
      canvas.onwheel = e => {if (!e.ctrlKey || !bounds) return; e.preventDefault(); if (e.deltaY) changeZoom(e.deltaY > 0 ? 1.4 : .7, Math.max(0, Math.min(1, (e.offsetX-65)/(canvas.clientWidth-85))));};
      canvas.onmousemove = e => {if (!bounds) return; cursor = bounds[0]+Math.max(0,Math.min(1,(e.offsetX-65)/(canvas.clientWidth-85)))*(bounds[1]-bounds[0]); draw(); readout();};
      canvas.onmouseleave = () => {cursor = null; draw();};
    });
    statistics(); draw();
  }
  function statistics(){
    $('.metric-statistics',root).innerHTML=series.length?`<details><summary>Statistiche dei campioni per serie</summary><div class="table-wrap"><table><thead><tr><th>Serie</th><th>Campioni</th><th>Minimo</th><th>Media dei campioni</th><th>Massimo</th></tr></thead><tbody>${series.filter(s=>!hidden.has(s.key)).map(s=>{
      let low=Infinity,high=-Infinity,sum=0;for(const p of s.ps){low=Math.min(low,p.value);high=Math.max(high,p.value);sum+=p.value;}
      return `<tr><td>${esc(seriesLabel(s.ps[0]))} (${esc(s.ps[0].unit)})</td><td>${number(s.ps.length)}</td><td>${number(low)}</td><td>${number(sum/s.ps.length)}</td><td>${number(high)}</td></tr>`;
    }).join('')}</tbody></table></div><p class="muted">Medie aritmetiche dei campioni nell’intera selezione. Nel registro chiamate il MOS medio è invece pesato sulla durata.</p></details>`:'';
  }
  function changeZoom(factor, fraction = .5) {
    if (!bounds) return;
    const span = Math.max(10, (bounds[1]-bounds[0]) * factor);
    const center = bounds[0] + fraction * (bounds[1]-bounds[0]);
    zoom = [center-span*fraction, center+span*(1-fraction)];
    cursor = null;
    draw();
  }
  function draw() {
    if (disposed || !root.isConnected) return;
    let lo = Infinity, hi = -Infinity;
    for (const p of points) {lo=Math.min(lo,xvalue(p)); hi=Math.max(hi,end(p));}
    if (!Number.isFinite(lo)) {bounds=null; return;}
    bounds = zoom || [lo,Math.max(lo+1000,hi)];
    panels.forEach((panel,i) => {
      const canvas = $(`[data-panel="${i}"]`,root), w = canvas.clientWidth, h = canvas.clientHeight, dpr = window.devicePixelRatio || 1;
      canvas.width=w*dpr; canvas.height=h*dpr; const ctx=canvas.getContext('2d'); ctx.scale(dpr,dpr);
      const left=65,right=w-20,top=15,bottom=h-35, sx=x=>left+(x-bounds[0])/(bounds[1]-bounds[0])*(right-left);
      const visible=panel.ss.filter(s=>!hidden.has(s.key));
      const scale=chartScale(visible.flatMap(s=>s.ps.filter(p=>end(p)>=bounds[0]&&xvalue(p)<=bounds[1]).map(p=>p.value)),panel.ss[0].ps[0].unit);
      const sy=y=>bottom-(y-scale.low)/(scale.high-scale.low)*(bottom-top);
      ctx.font='11px Segoe UI'; ctx.fillStyle='#526474';
      for(const tick of scale.ticks) {const y=sy(tick); ctx.strokeStyle='#e3e9ed'; ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.textAlign='right';ctx.fillText(tick.toLocaleString('it-IT',{maximumSignificantDigits:10}),left-8,y+4);}
      for(let j=0;j<=4;j++){const t=bounds[0]+j*(bounds[1]-bounds[0])/4;ctx.textAlign='center';ctx.fillText($('.chart-axis',root).value==='absolute'?new Date(t).toISOString().slice(11,23):number(t/1000)+' s',sx(t),h-10);}
      ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top);ctx.clip();
      for(const s of visible){ctx.strokeStyle=s.color;ctx.fillStyle=s.color;ctx.lineWidth=1.6;ctx.setLineDash(s.index>=colors.length?[5,3]:[]);let prev=null;
        for(const p of s.ps){const x=xvalue(p),y=sy(p.value);if(x>bounds[1]||end(p)<bounds[0]){prev=null;continue;}
          ctx.beginPath();
          if(p.valid_until){ctx.moveTo(sx(x),y);ctx.lineTo(sx(end(p)),y);}
          else if(prev&&x-xvalue(prev)<=30000&&!['event','interval','episode'].includes(p.sample_kind)){ctx.moveTo(sx(xvalue(prev)),sy(prev.value));ctx.lineTo(sx(x),y);}
          ctx.stroke();ctx.beginPath();ctx.arc(sx(x),y,p.valid?2:4,0,Math.PI*2);ctx.fill();prev=p;
        }
      }
      if(cursor!==null){ctx.setLineDash([3,3]);ctx.strokeStyle='#526474';ctx.beginPath();ctx.moveTo(sx(cursor),top);ctx.lineTo(sx(cursor),bottom);ctx.stroke();}ctx.restore();
    });
  }
  function readout(){
    if(cursor===null)return;
    $('.multi-readout',root).innerHTML=`<strong>${$('.chart-axis',root).value==='absolute'?esc(new Date(cursor).toISOString().replace('T',' ')):esc(number(cursor/1000))+' s dalla prima evidenza'}</strong>`+series.filter(s=>!hidden.has(s.key)).map(s=>{
      const p=s.ps.find(p=>p.valid_until&&xvalue(p)<=cursor&&end(p)>cursor)||s.ps.reduce((best,p)=>!best||Math.abs(xvalue(p)-cursor)<Math.abs(xvalue(best)-cursor)?p:best,null);
      const present=p&&(p.valid_until?xvalue(p)<=cursor&&end(p)>cursor:Math.abs(xvalue(p)-cursor)<=2500);
      return `<p><strong>${esc(seriesLabel(s.ps[0]))}</strong>: ${present?`${esc(number(p.value))} ${esc(p.unit)}${p.valid?'':' · ANOMALO'} · ${esc(stamp(p.ts))}<br>${esc(p.filename)}:${esc(p.line_no)}${p.valid_until?' · valido fino a '+esc(p.valid_until):''}${p.evidence?'<br>'+p.evidence.map(e=>`evento ${esc(e.event_id)} · ${esc(e.filename)}:${esc(e.line)}`).join(' · '):''}`:'nessun campione (tolleranza ±2,5 s per i punti; intervallo effettivo per MOS)'}</p>`;
    }).join('');
  }
  async function load(){
    const own=++generation; $('.chart-status',root).textContent='Caricamento metriche…';
    const entries=[...selected];
    // Four workers bound concurrent requests even when the entire catalog is selected.
    let next=0;const results=new Array(entries.length);
    await Promise.all(Array.from({length:Math.min(4,entries.length)},async()=>{while(next<entries.length){const i=next++, [value,stat]=entries[i],key=params(value,stat).toString();if(!cache.has(key))cache.set(key,api('metrics?'+key).catch(e=>{cache.delete(key);throw e;}));results[i]=await cache.get(key);}}));
    if(disposed||own!==generation||!root.isConnected)return;
    points=results.flat().filter(p=>p.value!==null&&Number.isFinite(p.value)&&Number.isFinite(timeValue(p.ts)));
    const missing=entries.filter((_,i)=>!results[i].length).map(([value])=>titleFor(value));
    $('.chart-status',root).textContent=entries.length?`${entries.length} metriche selezionate · ${number(points.length)} campioni${missing.length?' · Senza campioni: '+missing.join('; '):''}`:'Seleziona una metrica con “Aggiungi metriche”.';
    $('.chart-notes',root).textContent='I vuoti oltre 30 s interrompono le linee; MOS e intervalli mantengono la validità temporale calcolata. '+(selected.has('vd.missing_packets')?'Missing packets: conteggio per evento NART, non percentuale né perdita definitiva. Non sommare gli eventi come pacchetti unici persi. ':'')+(selected.has('vd.silence_skipped')?'Silenzio skippato: contatore cumulativo, può azzerarsi. ':'');
    $('.multi-readout',root).textContent='Passa sul grafico: valori allo stesso istante, senza interpolare i dati mancanti.';
    const episodes=points.filter(p=>p.episode).map(p=>({...p.episode,side:`P${p.perspective_id} · ${p.label}`}));
    $('.metric-episodes',root).innerHTML=episodes.length?incidentTable({incidents:episodes,incident_warnings:[]}):'';
    layout();
  }
  $('.metric-search',root).oninput=controls;
  $('.chart-invalid',root).onchange=safe(async()=>{controls();await load();});
  $('.chart-duplicates',root).onchange=safe(async()=>{controls();await load();});
  $('.chart-axis',root).onchange=()=>{zoom=null;cursor=null;draw();};
  $('.zoom-in',root).onclick=()=>changeZoom(.7);
  $('.zoom-out',root).onclick=()=>changeZoom(1.4);
  $('.reset-zoom',root).onclick=()=>{zoom=null;cursor=null;draw();};
  const presets={quality:['derived.mos_reference|incoming','derived.mos_reference|outgoing'],network:['rtcp.rtt','rtcp.jitter|incoming','rtcp.loss|incoming'],receive:['derived.mos_reference|incoming','vd.silence_skipped','vd.missing_packets'],clear:[]};
  $$('[data-preset]',root).forEach(b=>b.onclick=safe(async()=>{selected.clear();for(const value of presets[b.dataset.preset])if(options.some(o=>o.value===value))selected.set(value,defaults(value.split('|')[0]).value);controls();await load();}));
  const observer=new ResizeObserver(draw);observer.observe($('.multi-panels',root));
  chartCleanup=()=>{disposed=true;generation++;observer.disconnect();};
  controls();await load();
}
