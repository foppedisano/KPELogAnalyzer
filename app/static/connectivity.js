"use strict";
const netColors={up:'#34875b',down:'#c94343',transient:'#d59a18',available:'#e6c65d',unknown:'#a6afb9'};
const netLabels={up:'UP osservato',down:'DOWN osservato',transient:'Transiente / parziale',available:'Interfaccia disponibile',unknown:'Non determinabile'};
const netLayers={network:'Rete · sintesi',device:'Dispositivo',stun:'Probe STUN',cti:'Servizio CTI',sip:'Servizio SIP',media:'Ricezione media',app:'Stato app/KPE'};
const switchColor='#783cc7';
function switchDetails(s){return `<div class="switch-evidence"><strong>⇄ ${esc(s.label)}</strong><p>${esc(s.ts)} · richiesta esplicita al KPE, completamento non verificato.</p><p>${s.transition_basis==='explicit_fields'?'Da/a dichiarati nel messaggio.':s.transition_basis==='nearby_interface_observations'?'Da/a: sequenza delle interfacce osservate entro ±3 s, non campi del marker.':'Transizione non dichiarata o contesto ambiguo: nessun cambio di tecnologia radio dedotto.'}</p>${s.association==='unassigned_source_context'?'<p>Evento della sorgente; chiamata non attribuibile in modo univoco.</p>':''}${(s.evidence||[]).map(e=>`<p>Evento #${e.event_id} · ${esc(e.filename)}:${e.line}</p>`).join('')}${(s.network_context||[]).length?`<details><summary>Interfacce osservate nel contesto</summary>${s.network_context.map(e=>`<p>${esc(e.ts)} · ${esc(e.state)} · ${esc(e.filename)}:${e.line} · evento #${e.event_id}</p>`).join('')}</details>`:''}</div>`;}
function switchReadout(source,t){return (source.network_switches||[]).filter(s=>Math.abs(timeValue(s.ts)-t)<=2500).map(switchDetails).join('');}
function switchList(source){const items=source.network_switches||[];return items.length?`<details class="switch-list"><summary>⇄ ${items.length} Switch Network espliciti · ${esc(source.label||'sorgente')}</summary>${items.map(s=>`<details><summary>${esc(s.ts)} · ${esc(s.label)}</summary>${switchDetails(s)}</details>`).join('')}</details>`:'';}
function drawSwitchMarkers(ctx,source,range,x,top,height,transform){
  ctx.save();ctx.globalAlpha=1;ctx.strokeStyle=switchColor;ctx.fillStyle=switchColor;ctx.lineWidth=2;let lastLabel=-Infinity;
  for(const s of source.network_switches||[]){const t=transform(source,s.ts);if(t<range[0]||t>range[1])continue;const px=x(t);
    ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(px,top+10);ctx.lineTo(px,top+height);ctx.stroke();ctx.setLineDash([]);
    ctx.beginPath();ctx.moveTo(px,top);ctx.lineTo(px+6,top+6);ctx.lineTo(px,top+12);ctx.lineTo(px-6,top+6);ctx.closePath();ctx.fill();
    if(px-lastLabel>90){ctx.font='bold 11px system-ui';ctx.textAlign='left';ctx.fillText('⇄ Switch',px+9,top+10);lastLabel=px;}
  }ctx.restore();
}
function netEvidence(data,ids){return ids.map(id=>{const e=data.evidence[id];return e?`${esc(e.filename)}:${e.line_no} · evento #${id} · ${esc(e.ts)}`:`evento #${id}`;}).join('<br>');}
function netAt(data,t,layer='network'){return data.lanes[layer]?.find(s=>timeValue(s.start)<=t&&t<timeValue(s.end));}
function netReadout(data,t){return Object.entries(netLayers).map(([layer,label])=>{const s=netAt(data,t,layer);return `<p><strong>${esc(label)}: ${esc(netLabels[s?.state]||netLabels.unknown)}</strong> · ${esc(s?.reason||'Fuori copertura')}<br>${s?netEvidence(data,s.evidence):''}</p>`;}).join('');}
// Each source gets its own stripe: never average contradictory phones.
function drawNetBands(ctx,data,range,x,top,height,transform){
  if(!data.length)return;
  ctx.save();
  data.forEach((source,i)=>{const y=top+i*height/data.length;
    for(const s of source.lanes.network){const a=Math.max(range[0],transform(source,s.start)),b=Math.min(range[1],transform(source,s.end));if(b<=a)continue;ctx.fillStyle=netColors[s.state]||netColors.unknown;ctx.globalAlpha=.18;ctx.fillRect(x(a),y,x(b)-x(a),height/data.length);}
    drawSwitchMarkers(ctx,source,range,x,y,height/data.length,transform);
  });ctx.restore();
}
async function mountConnectivity(root,params,provided=null){
  root.innerHTML='<p role="status">Caricamento situazione rete…</p>';
  const response=provided??await api('connectivity?'+new URLSearchParams(params));if(!root.isConnected)return;
  const sources=Array.isArray(response)?response:[response];
  root.innerHTML=`<div class="panel"><div class="panel-head"><h2>Rete e servizi nel tempo</h2></div><div class="panel-body"><p>Verde: risposta osservata · giallo: transiente/parziale · rosso: indisponibilità osservata · grigio: non determinabile. Una risposta CTI o SIP prova quel percorso, non tutti i servizi. Le evidenze scadono dopo 30 s; il silenzio dei log non vale UP. Clic, puntatore o cursore temporale mostrano le prove.</p><div class="net-sources"></div></div></div>`;
  const area=$('.net-sources',root);
  for(const data of sources){
    const section=document.createElement('section');section.className='net-source';
    section.innerHTML=`<h3>${esc(data.label)}${data.perspective_id?' · P'+data.perspective_id:''}</h3><p>${esc(data.start)} → ${esc(data.end)}</p><p class="switch-key">◆ ⇄ Switch Network · evento puntuale, non stato UP/DOWN</p><canvas class="net-canvas" role="img" aria-label="Timeline Switch Network, rete, dispositivo, STUN, CTI, SIP, media e app"></canvas><label>Istante da esaminare <input class="net-slider" type="range" min="0" max="${Math.max(1,Math.ceil((timeValue(data.end)-timeValue(data.start))/1000)-1)}" step="1" value="0"></label>${switchList(data)}<div class="net-readout"></div>`;
    area.append(section);
    const canvas=$('canvas',section),start=timeValue(data.start),end=timeValue(data.end),ctx=canvas.getContext('2d');
    function read(t){$('.net-readout',section).innerHTML=`<strong>${esc(new Date(t).toISOString().replace('T',' ').slice(0,23))}</strong>`+switchReadout(data,t)+netReadout(data,t);}
    function draw(){const w=Math.max(300,canvas.clientWidth),h=270,dpr=window.devicePixelRatio||1;canvas.style.height=h+'px';canvas.width=w*dpr;canvas.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.font='12px system-ui';ctx.translate(0,30);
      Object.entries(netLayers).forEach(([layer,label],i)=>{const y=i*30;ctx.fillStyle='#263746';ctx.fillText(label,0,y+17);for(const s of data.lanes[layer]){const a=145+(timeValue(s.start)-start)/(end-start)*(w-155),b=145+(timeValue(s.end)-start)/(end-start)*(w-155);ctx.fillStyle=netColors[s.state];ctx.fillRect(a,y+3,Math.max(.5,b-a),21);}});
      ctx.fillStyle='#263746';ctx.fillText(data.start.slice(11,19),145,232);ctx.textAlign='right';ctx.fillText(data.end.slice(11,19),w-10,232);ctx.textAlign='left';ctx.translate(0,-30);ctx.fillStyle=switchColor;ctx.fillText('⇄ Switch Network',0,17);drawSwitchMarkers(ctx,data,[start,end],t=>145+(t-start)/(end-start)*(w-155),4,236,(_,ts)=>timeValue(ts));}
    function point(e){const f=Math.max(0,Math.min(.999999,(e.offsetX-145)/(Math.max(300,canvas.clientWidth)-155)));const sec=Math.floor(f*(end-start)/1000);$('.net-slider',section).value=sec;read(Math.min(end-1,start+sec*1000));}
    canvas.onmousemove=point;canvas.onclick=point;$('.net-slider',section).oninput=e=>read(Math.min(end-1,start+Number(e.target.value)*1000));
    draw();const focus=params.focus?Math.max(start,Math.min(end-1,timeValue(params.focus))):start;$('.net-slider',section).value=Math.floor((focus-start)/1000);read(focus);
  }
  if(!sources.length)area.innerHTML='<p>Nessuna finestra di chiamata delimitabile. Usa una sorgente e un periodo nella vista Rete e servizi.</p>';
}
async function attemptDetail(c){
  if(chartCleanup){chartCleanup();chartCleanup=null;}const token=++renderToken;state.current=c.id;
  window.scrollTo(0,0);
  $('#breadcrumb').textContent=recordReference(c);
  $('#page').innerHTML=`<button id="attempt-back">← Registro chiamate</button>${title(recordReference(c),esc(c.callee||'Destinatario non registrato'),esc(c.reason))}<div class="panel"><p>${esc(c.label)} · ${esc(c.start)}</p><p>${esc(c.filename)}:${c.line_no} · evento #${c.event_id}${c.reason_event_id?' · prova del blocco #'+c.reason_event_id:''}</p><p>Voce separata dalle sessioni SIP. Non viene collegata a una chiamata soltanto per vicinanza temporale o numero. Un tentativo accettato dall’app può comparire anche come sessione SIP nel registro.</p></div><div id="attempt-net"></div><p class="muted">Prove del tentativo e contesto opzionale della stessa sorgente. I controlli Tutto non creano associazioni a sessioni SIP.</p><div id="attempt-events"></div>`;
  $('#attempt-back').onclick=safe(()=>setView('calls'));
  const t=timeValue(c.start),format=n=>new Date(n).toISOString().slice(0,23).replace('T',' ');
  await mountConnectivity($('#attempt-net'),{import:c.import_id,start:format(t-60000),end:format(t+120000),focus:c.start});
  if(token!==renderToken)return;
  await mountEvents($('#attempt-events'),{attempt:c.event_id},"attempt");
}
async function renderNetwork(page){
  const imports=await api('imports');if(!page.isConnected)return;
  page.innerHTML=title('CONNETTIVITÀ','Rete e servizi','Esamina anche i periodi fuori chiamata e i tentativi bloccati.')+`<div class="panel toolbar"><label>Sorgente<select id="net-import">${imports.map(i=>`<option value="${i.id}">${esc(i.label)}</option>`).join('')}</select></label><label>Da (orario log)<input id="net-start" type="datetime-local" step="1"></label><label>A<input id="net-end" type="datetime-local" step="1"></label><button id="net-run">Analizza periodo</button></div><div id="net-result"></div>`;
  function defaults(){const p=state.perspectives.find(p=>p.import_id===+$('#net-import').value&&p.start);if(p){$('#net-start').value=p.start.slice(0,19).replace(' ','T');$('#net-end').value=new Date(timeValue(p.start)+600000).toISOString().slice(0,19);}}
  $('#net-import').onchange=defaults;defaults();
  $('#net-run').onclick=safe(()=>mountConnectivity($('#net-result'),{import:$('#net-import').value,start:$('#net-start').value.replace('T',' '),end:$('#net-end').value.replace('T',' ')}));
}
