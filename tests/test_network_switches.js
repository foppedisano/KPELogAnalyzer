const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const box={timeValue:s=>Date.parse(s.replace(' ','T')+'Z'),esc:s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')};
vm.createContext(box);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/connectivity.js'),'utf8'),box);
test('switch rendering escapes source evidence and retains ambiguous status',()=>{
  const html=box.switchDetails({label:'<img onerror=evil>',ts:'2026-01-01',association:'unassigned_source_context',
    evidence:[{event_id:1,filename:'<script>',line:2}],network_context:[]});
  assert.ok(!html.includes('<img'));assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('non attribuibile'));assert.ok(html.includes('non dichiarata'));
});
test('switch markers use the source transform and exclude out-of-view events',()=>{
  const moves=[],labels=[];
  const ctx=new Proxy({moveTo:(x,y)=>moves.push([x,y]),fillText:t=>labels.push(t)},{get:(o,k)=>k in o?o[k]:(()=>{})});
  const source={offset:2,network_switches:[{ts:5},{ts:25}]};
  box.drawSwitchMarkers(ctx,source,[0,10],t=>t*10,20,100,(s,t)=>t+s.offset);
  assert.deepEqual(moves[0],[70,30]);assert.equal(labels.length,1);
});
test('readout shows only markers close to the cursor, without changing timestamps',()=>{
  const source={network_switches:[{ts:'2026-01-01 12:00:10.000',label:'Switch Network',evidence:[]}]};
  assert.ok(box.switchReadout(source,box.timeValue('2026-01-01 12:00:10.000')).includes('Switch Network'));
  assert.equal(box.switchReadout(source,box.timeValue('2026-01-01 12:00:14.000')),'');
});
