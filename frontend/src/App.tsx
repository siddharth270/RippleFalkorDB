import { useEffect, useRef, useState } from 'react';
import './style.css';

type Node = {id:string;labels:string[];properties:Record<string,any>};
type Edge = {source:string;target:string;type:string};
type Scene = {nodes:Node[];edges:Edge[];evidence:any[]};
type Event = {index:number;type:string;scene:Scene;[key:string]:any};
const titles:Record<string,string>={healthy_8:'Standby ready · 8 units',healthy_5:'Limited standby · 5 units',standby_down:'Standby unavailable',stale_valve:'Stale valve evidence',stuck_valve:'Stuck bypass valve',new_load:'New critical load · 9 units'};
const label=(s:string)=>s.replace(/_/g,' ');

function Facility({scene,graphMode}:{scene?:Scene;graphMode:boolean}){
 if(!scene) return <div className="waiting"><div className="orbit"/><h2>Ready to investigate.</h2><p>Choose a fault scenario and start a live run.<br/>The robot will act on evidence retrieved from FalkorDB.</p></div>;
 const locations=scene.nodes.filter(n=>n.labels.includes('Location'));
 const assets=scene.nodes.filter(n=>n.labels.includes('Asset'));
 const positions:Record<string,[number,number]>={};
 locations.forEach(n=>positions[n.id]=[80+Number(n.properties.x)*90,230-Number(n.properties.y)*64]);
 assets.forEach(n=>{
  const loc=scene.edges.find(e=>e.type==='LOCATED_IN'&&e.source===n.id)?.target;
  const siblings=assets.filter(a=>scene.edges.some(e=>e.type==='LOCATED_IN'&&e.source===a.id&&e.target===loc));
  const idx=siblings.findIndex(a=>a.id===n.id); const base=positions[loc||'']||[350,230];
  positions[n.id]=[base[0],base[1]+(idx-(siblings.length-1)/2)*61];
 });
 const get=(id:string,prop:string)=>scene.evidence.find(o=>o.asset_id===id&&o.property===prop);
 const at=scene.edges.find(e=>e.type==='AT'); const robot=positions[at?.target||'dock'];
 return <svg className="facility" viewBox="0 0 730 470" role="img" aria-label={graphMode?'FalkorDB operational dependency graph':'Facility and verified robot location'}>
  <defs><pattern id="grid" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M 22 0 L 0 0 0 22" fill="none" stroke="#20343d" strokeWidth=".5"/></pattern><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7" fill="#538c91"/></marker></defs>
  <rect width="730" height="470" fill="url(#grid)"/>
  {scene.edges.filter(e=>e.type==='ADJACENT_TO').map((e,i)=>{const a=positions[e.source],b=positions[e.target];return a&&b&&<line key={'r'+i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#344e5c" strokeWidth="18" opacity=".4"/>})}
  {locations.map(n=><g key={n.id}><text x={positions[n.id][0]} y={positions[n.id][1]-85} textAnchor="middle" className="zone">{n.properties.name}</text></g>)}
  {scene.edges.filter(e=>e.type==='FEEDS').map((e,i)=>{const a=positions[e.source],b=positions[e.target];return a&&b&&<g key={i}><line x1={a[0]+35} y1={a[1]} x2={b[0]-42} y2={b[1]} stroke="#538c91" strokeWidth={graphMode?2:3} markerEnd="url(#arrow)"/>{graphMode&&<text x={(a[0]+b[0])/2} y={(a[1]+b[1])/2-7} className="edge-label">FEEDS</text>}</g>})}
  {assets.map(n=>{const [x,y]=positions[n.id];const obs=get(n.id,'health')||get(n.id,'position')||get(n.id,'flow')||get(n.id,'running');const bad=obs?.value==='failed';return <g key={n.id}><rect x={x-49} y={y-23} width="98" height="46" rx="7" fill={bad?'#3d252c':'#112c36'} stroke={bad?'#e87977':'#426471'}/><text x={x} y={y-4} textAnchor="middle" className="asset-name">{n.properties.name.replace(' supply','').replace(' valve','').replace(' isolation','')}</text><text x={x} y={y+12} textAnchor="middle" className={bad?'bad-text':'asset-value'}>{obs?obs.fresh===false?`stale: ${String(obs.value)}`:`${obs.property}: ${String(obs.value)}`:n.properties.demand?`demand ${n.properties.demand} · unobserved`:'unobserved'}</text></g>})}
  {robot&&<g className="robot" transform={`translate(${robot[0]-52},${robot[1]+39})`}><circle r="14" fill="#a7efca"/><path d="M-7 -4H7V5H-7ZM-5 5V9M5 5V9" stroke="#0a242a" strokeWidth="2" fill="none"/><text x="0" y="28" textAnchor="middle" fill="#a7efca" fontSize="10">INSPECTOR</text></g>}
  <text x="22" y="450" className="edge-label">{graphMode?'Directed operational relationships from live Cypher queries':'Synthetic equipment · location-gated observations · verified waypoints'}</text>
 </svg>
}
export default function App(){
 const [scenario,setScenario]=useState('healthy_5'),[adapter,setAdapter]=useState('mock'),[mode,setMode]=useState('full_ripple');
 const [events,setEvents]=useState<Event[]>([]),[run,setRun]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [cursor,setCursor]=useState(-1),[graphMode,setGraphMode]=useState(false),[db,setDb]=useState('Connecting');
 const socket=useRef<WebSocket|null>(null);
 useEffect(()=>{fetch('/api/health').then(r=>{if(!r.ok)throw Error();setDb('FalkorDB connected')}).catch(()=>setDb('Database unavailable'));return()=>socket.current?.close()},[]);
 const active=cursor<0?events.length-1:cursor;
 const shown=events.slice(0,active+1); const event=shown[shown.length-1];
 const branches=[...shown].reverse().find(e=>e.type==='branches')?.plans||[];
 const decision=[...shown].reverse().find(e=>e.type==='decision');
 const result=shown.some(e=>e.type==='complete')?run?.result:null;
 async function start(){
  setBusy(true);setError('');setEvents([]);setRun(null);setCursor(-1);socket.current?.close();
  try{
   const res=await fetch('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario,adapter,mode,paced:true})});
   const data=await res.json();if(!res.ok)throw Error(data.detail||'Unable to start');
   const ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/stream/${data.id}`);socket.current=ws;
   ws.onmessage=msg=>{const packet=JSON.parse(msg.data);if(packet.kind==='event')setEvents(e=>[...e,packet.event]);else{setRun(packet.run);setBusy(false);if(packet.run.error)setError(packet.run.error)}};
   ws.onerror=()=>{setError('Live connection interrupted. The backend may still be running.');setBusy(false)};
   ws.onclose=()=>{fetch(`/api/runs/${data.id}`).then(r=>r.json()).then(r=>{setRun(r);setEvents(r.events||[]);setBusy(r.status==='running');if(r.error)setError(r.error)}).catch(()=>{})};
  }catch(e){setError(String(e));setBusy(false)}
 }
 function download(){const blob=new Blob([JSON.stringify({...run,events},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`ripple-${scenario}-trace.json`;a.click();URL.revokeObjectURL(a.href)}
 return <main><header><div className="brand"><span className="brand-mark">R</span><div><strong>RIPPLE</strong><small>EVIDENCE BEFORE INTERVENTION</small></div></div><div className="connection"><i/>{db}</div><a href="https://cyberwave.com/s-team-9/envs/graph-hacks" target="_blank" rel="noreferrer">Open Cyberwave ↗</a></header>
 <section className="intro"><div><span className="eyebrow">PHYSICAL AI / INCIDENT RESPONSE</span><h1>One fault. Connected consequences.</h1><p>Inspect the uncertainty. Compare possible interventions. Verify the recovery.</p></div><span className="pill">{adapter==='mock'?'LOCAL DISCRETE SIMULATION':'CYBERWAVE · TWIN REPOSITIONING'}</span></section>
 <section className="controls"><label>FAULT SCENARIO<select value={scenario} disabled={busy} onChange={e=>setScenario(e.target.value)}>{Object.entries(titles).map(([id,title])=><option key={id} value={id}>{title}</option>)}</select></label><label>ROBOT<select value={adapter} disabled={busy} onChange={e=>setAdapter(e.target.value)}><option value="mock">Local simulated inspector</option><option value="cyberwave">Cyberwave Go2 twin</option></select></label><label>POLICY<select value={mode} disabled={busy} onChange={e=>setMode(e.target.value)}><option value="full_ripple">Full Ripple</option><option value="graph_no_inspection">Graph / no diagnosis inspection</option><option value="local_baseline">Local reactive baseline</option></select></label><button className="primary" disabled={busy||db!=='FalkorDB connected'} onClick={start}>{busy?'Investigating…':'Inject fault & run →'}</button></section>
 {error&&<div role="alert" className="error">{error}</div>}
 <div className="dashboard"><section className="panel world"><div className="panel-title"><h2>Facility digital twin</h2><div className="tabs"><button className={!graphMode?'selected':''} onClick={()=>setGraphMode(false)}>Facility</button><button className={graphMode?'selected':''} onClick={()=>setGraphMode(true)}>Dependencies</button></div></div><Facility scene={event?.scene} graphMode={graphMode}/><div className="playback"><span>{busy?'LIVE':events.length?'RECORDED RUN':'AWAITING RUN'}</span><input aria-label="Replay event" type="range" min="0" max={Math.max(events.length-1,0)} value={Math.max(active,0)} disabled={busy||!events.length} onChange={e=>setCursor(Number(e.target.value))}/><span>{events.length?`${active+1} / ${events.length}`:'0 events'}</span><button disabled={!events.length||busy} onClick={()=>setCursor(-1)}>Latest</button></div></section>
 <aside className="panel plans"><div className="panel-title"><h2>Possible interventions</h2><span className="tag">GRAPH.COPY</span></div><p className="caption">Each candidate is checked in an isolated graph snapshot. Predicted effects never become live evidence.</p>{branches.length?branches.map((p:any)=><article className={`plan ${p.name===decision?.chosen_plan?'chosen':''}`} key={p.name}><div><strong>{label(p.name)}</strong><span className={p.status==='rejected'?'bad-text':''}>{p.name===decision?.chosen_plan?'SELECTED':p.status.toUpperCase()}</span></div><p>{p.actions.map(label).join(' → ')}</p>{p.reasons.length>0&&<details><summary>Why {p.status}?</summary>{p.reasons.map((r:string,i:number)=><p key={i}>{r}</p>)}</details>}</article>):<p className="placeholder">Candidate checks appear when the incident begins.</p>}</aside></div>
 <section className="metrics"><div><small>RECOVERY</small><strong className={result&&!result.recovered?'bad-text':''}>{result?(result.recovered?'Verified':'Not recovered'):busy?'In progress':'—'}</strong></div><div><small>OBSERVED FLOW / DEMAND</small><strong>{result?.service?.flow!=null?`${result.service.flow} / ${result.service.required}`:'—'}<em> units</em></strong></div><div><small>INSPECTIONS</small><strong>{shown.filter(e=>e.type==='inspection').length}</strong></div><div><small>VERIFICATION FAILURES</small><strong>{shown.filter(e=>e.type==='verification'&&e.status==='failed').length}</strong></div></section>
 <div className="bottom"><section className="panel"><div className="panel-title"><h2>Evidence & execution timeline</h2><button disabled={!run||busy} onClick={download}>Export trace ↓</button></div><div className="timeline">{shown.length?shown.map(e=><div key={e.index} className="event"><span>{String(e.index+1).padStart(2,'0')}</span><div><b>{label(e.type)}</b><p>{e.type==='move'?`Verified arrival at ${label(e.location_id)}`:e.type==='inspection'?`${label(e.ip_id)} · ${e.purpose} · ${e.observations.map((o:any)=>`${o.property}=${o.value}`).join(', ')}`:e.type==='verification'?`${label(e.action)}: ${e.status}`:e.type==='decision'?label(e.chosen_plan||'No feasible plan'):e.type==='branches'?`${e.plans.length} candidate snapshots evaluated and cleaned up`:e.type==='impact'?`Shared assets: ${e.impact.shared_with.join(', ')} · critical services: ${e.impact.critical_services.join(', ')}`:e.type==='inspection_ranking'?`Next inspection: ${e.ranking[0]?.ip_id||'none'} · decision relevance heuristic`:e.type==='complete'?e.recovered?'Service recovery confirmed by observation':'Recovery not confirmed':e.message||titles[e.scenario]}</p></div></div>):<p className="placeholder">Live events will show the evidence behind each action.</p>}</div></section><section className="panel rationale"><div className="panel-title"><h2>Recorded decision</h2><span className="tag">PROVENANCE</span></div><p className="caption">Built from the persisted Decision trace, not generated claims.</p><pre>{decision?.explanation||'The decision record will appear after the required evidence is gathered.'}</pre><p className="disclosure">Simulation scope: simplified cooling capacity and synthetic sensors. Cyberwave mode repositions the twin and independently reads its stored pose; it does not demonstrate walking, hydraulic physics, or physical valve manipulation.</p></section></div>
 <footer>RIPPLE · FalkorDB + Cyberwave <span>Hypotheses are evidence, not proof. Graph snapshots are predictions, not physics.</span></footer></main>
}
