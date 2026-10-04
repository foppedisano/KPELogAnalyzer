"use strict";
async function renderMos(page, renderId) {
  const ps = state.perspectives;
  const opts = ps.map(p => `<option value="${p.id}">P${p.id} · chiamata #${p.call_id} · ${esc(p.label)} · ${stamp(p.start)}</option>`).join('');
  page.innerHTML = title('QUALITÀ DEL TRASPORTO RTP','MOS e ricezione','Profilo fisso basato sulla perdita. Silenzio saltato, missing packets, jitter e RTT restano evidenze separate.') +
    `<div class="panel panel-body"><label>Ruolo della sorgente locale<select id="mos-role"><option value="app">App</option><option value="gw">GW</option></select></label><label>Ricevitore locale<select id="mos-local">${opts}</select></label><label>Ricevitore opposto della stessa tratta<select id="mos-peer"><option value="">Non disponibile: usa i Receiver Report RTCP locali</option>${opts}</select></label><p>Selezionando il ricevitore opposto dichiari che le due prospettive osservano i lati opposti della stessa tratta. Nessuna associazione è dedotta dagli orari o dai numeri.</p><button id="mos-apply">Applica sorgenti</button> <button id="mos-export" disabled>Esporta analisi JSON</button><div id="mos-result"></div></div>`;
  if (!ps.length) { $('#mos-result',page).textContent='Importa i log per iniziare.'; return; }
  if (window.mosLocal && ps.some(p=>p.id===window.mosLocal)) $('#mos-local',page).value=window.mosLocal;
  let result, request=0;
  const proof = m => (m.evidence || [{event_id:m.event_id,filename:m.filename,line:m.line_no}]).map(e=>`evento ${e.event_id}, ${e.filename}:${e.line}`).join('; ');
  function chart(data) {
    if(!data.length) return '<p>Nessuna stima: mancano report di perdita validi e attribuiti con intervallo utilizzabile.</p>';
    const groups=new Map();
    data.forEach(m=>{const key=`P${m.perspective_id} · flow ${m.flow} · SSRC ${m.ssrc||'ignoto'}`;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(m);});
    return [...groups].map(([key,points])=>{
      const all=[...result.downstream,...result.upstream];
      const aligned=(m,field)=>timeValue(m[field])+m.clock_offset*1000;
      const start=all.reduce((v,m)=>Math.min(v,aligned(m,'ts')),Infinity), end=all.reduce((v,m)=>Math.max(v,aligned(m,'valid_until')),-Infinity);
      const x=t=>50+900*(t-start)/(end-start||1), y=v=>145-(v-1)*30;
      const duration=points.reduce((s,m)=>s+m.interval_seconds,0);
      const mean=points.reduce((s,m)=>s+m.value*m.interval_seconds,0)/duration;
      return `<h3>${esc(key)}</h3><p>Media pesata sugli intervalli coperti: ${number(mean)} · durata coperta ${number(duration)} s · offset sorgente ${number(points[0].clock_offset)} s (asse allineato; tooltip con orari originali)</p><svg viewBox="0 0 1000 180" role="img" aria-label="MOS a gradini da 1 a 5, indice senza unità"><text x="5" y="13" font-size="11">MOS</text>${[1,2,3,4,5].map(v=>`<text x="10" y="${y(v)}">${v}</text><path d="M40 ${y(v)} H960" stroke="#ddd"/>`).join('')}${points.map(m=>`<path d="M${x(aligned(m,'ts'))} ${y(m.value)} H${x(aligned(m,'valid_until'))}" stroke="#008d86" stroke-width="3"><title>${esc(`${m.ts} → ${m.valid_until}\nMOS ${number(m.value)} · perdita ${number(m.loss_percent)}%\n${proof(m)}`)}</title></path>`).join('')}<text x="50" y="175">${new Date(start).toISOString().slice(0,19)}</text><text x="730" y="175">${new Date(end).toISOString().slice(0,19)}</text></svg>`;
    }).join('');
  }
  async function load() {
    const token=++request; $('#mos-export',page).disabled=true;
    const local=$('#mos-local',page).value, peer=$('#mos-peer',page).value, role=$('#mos-role',page).value;
    $('#mos-result',page).textContent='Calcolo…';
    try {
      const data=await api(`mos?local=${local}&local_role=${role}${peer?'&peer='+peer:''}`);
      if(renderId!==renderToken || token!==request || !page.isConnected || !$('#mos-result',page))return;
      result=data; window.mosLocal=+local;
      const basis={local:'ricezione locale',peer_local_reused:'ricezione locale del lato opposto riutilizzata',remote_rtcp:'stima dai Receiver Report remoti'};
      $('#mos-result',page).innerHTML=`<p>${esc(data.model.description)} G.711 · 10 ms · PLC Appendix I · ${esc(data.model.version)}</p><h2>Downstream · ${basis[data.downstream_basis]}</h2>${chart(data.downstream)}<h2>Upstream · ${basis[data.upstream_basis]}</h2>${chart(data.upstream)}<p>${data.limitations.map(esc).join(' ')}</p><h2>Evidenze dei ricevitori</h2><p>Delta silenzio in ms; rapporto sulla durata osservata, non percentuale di voce persa. Missing packets non sommati alla perdita RTCP. Prime 300 osservazioni; JSON completo.</p><div class="table-wrap"><table><thead><tr><th>Ricevitore</th><th>Orario</th><th>Parametro</th><th>Valore</th><th>Contesto / evidenza</th></tr></thead><tbody>${data.context.slice(0,300).map(m=>`<tr><td>P${m.perspective_id} · ${m.perspective_id===+local?role:(role==='app'?'gw':'app')}</td><td>${esc(m.ts)}</td><td>${esc(m.name)} · ${esc(m.direction)} · ${esc(m.device||m.flow)}</td><td>${number(m.value)} ${esc(m.unit)}${m.name==='derived.silence_delta'?` · ${number(m.value/(m.interval_seconds*10))}% su ${number(m.interval_seconds)} s`:''}</td><td>${esc(proof(m))}</td></tr>`).join('')}</tbody></table></div>`;
      $('#mos-export',page).disabled=false;
    } catch(e) {if(renderId===renderToken && token===request && $('#mos-result',page)) $('#mos-result',page).textContent=e.message;}
  }
  $('#mos-apply',page).onclick=safe(load);
  $('#mos-export',page).onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='mos-analysis.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  await load();
}
