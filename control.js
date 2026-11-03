(()=>{
const $=id=>document.getElementById(id),nativeFetch=window.fetch.bind(window);
let token='',last=null,ready;
const escaped=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>Number(n||0).toLocaleString(undefined,{maximumFractionDigits:2});
const age=t=>t?`${Math.max(0,Math.round((Date.now()/1000-t)/60))} min ago`:'no checkpoint';
window.fetch=async(input,init={})=>{if(init.method?.toUpperCase()==='POST' && new URL(input,location.href).origin===location.origin){await ready;init={...init,headers:{...init.headers,'X-Hunter-Control':token}}}return nativeFetch(input,init)};
async function refresh(){try{
 const response=await nativeFetch('/control/status');if(!response.ok)throw Error('open through the control room on port 8767');const s=await response.json();token=s.token;last=s;
 if(s.readonly){document.querySelectorAll('button,input,select').forEach(e=>e.disabled=true);}
 const cloud=s.cloud||{},runs=cloud.runs||[],jobs=runs.flatMap(r=>r.jobs||[]);
 $('cloud-count').textContent=jobs.filter(j=>j.status==='in_progress').length;
 $('cloud-queued').textContent=jobs.filter(j=>j.status==='queued').length;
 $('cloud-sync-age').textContent=age(cloud.updated);
 $('control-task').textContent=s.readonly?'read-only Wi-Fi view · controls available on the Mac':s.task?.name?`${s.task.name}: ${s.task.status}${s.task.error?' · '+s.task.error:''}`:'ready';
 $('fleet-runs').innerHTML=runs.map((r,i)=>`<details class="fleet-run" ${i===0?'open':''}><summary><span>${escaped(r.branch)}</span><span>${escaped(r.conclusion||r.status)}</span></summary><div class="control-line"><a href="${escaped(r.url)}" target="_blank" rel="noopener">run ${r.id}</a>${r.status!=='completed'?`<button data-stop="${r.id}">stop campaign</button>`:''}</div><table><thead><tr><th>worker</th><th>state</th></tr></thead><tbody>${r.jobs.map(j=>`<tr><td>${escaped(j.name)}</td><td>${escaped(j.conclusion||j.status)}</td></tr>`).join('')}</tbody></table>${(r.checkpoints||[]).map(c=>`<div class="frontier-note">shard ${c.shard} · ${escaped(c.arm)} · ${fmt(c.native?.found_session)} segment candidates · ${c.tested_campaign==null?'legacy checkpoint; CPU metrics unavailable':`${fmt(c.tested_campaign)} campaign tests · ${fmt(c.tested_per_cpu_hour)} tests / sampled CPU-hour · ${Math.round((c.search_seconds||0)/60)} / ${Math.round((c.planned_seconds||1800)/60)} min search`} · checkpoint ${age(c.updated)}</div>`).join('')}</details>`).join('')||'<p class="muted">sync to load cloud campaigns.</p>';
 for(const b of document.querySelectorAll('[data-stop]'))b.onclick=()=>action('stop',{run:+b.dataset.stop});
 const m=s.brain||{};$('brain-count').textContent=fmt(m.rows);$('brain-mode').textContent=m.mode||'untrained';$('brain-version').textContent=m.id?m.id.slice(0,12):'—';
 $('brain-prospective').textContent=s.prospective?.length?`fresh cloud test: ${fmt(s.prospective[0].n)} observations · gain vs calibrated baseline ${((s.prospective[0].gain_vs_calibrated||0)*100).toFixed(1)}%`:'prospective cloud evaluation pending';
 $('brain-learning-check').textContent=s.learning_checks?.length?`cumulative learning test: ${((s.learning_checks[0].candidate_gain||0)*100).toFixed(2)}% error improvement vs the original frozen model on ${fmt(s.learning_checks[0].n)} new observations`:'cumulative learning test: collecting a fresh campaign; model decisions remain shadow-only';
 $('brain-details').textContent=m.architecture?`${m.architecture} · trained ${age(m.updated)} · ${fmt(m.elapsed_s)}s including data preparation`:'No model has been trained yet.';
 $('brain-metrics').innerHTML=Object.entries(m.metrics||{}).map(([split,v])=>`<tr><td>${escaped(split)}</td><td>${fmt(v.n)}</td><td>${v.baseline_mse.toFixed(5)}</td><td>${v.calibrated_baseline_mse?.toFixed(5)||'—'}</td><td>${v.model_mse.toFixed(5)}</td><td>${v.relative_gain==null?'—':(100*v.relative_gain).toFixed(1)+'%'}</td></tr>`).join('');
 $('experiment-rows').innerHTML=(s.experiments?.experiments||[]).map(e=>`<tr><td>${escaped(e.name)}</td><td><span class="badge b-dim">${escaped(e.status)}</span></td><td>${escaped(e.evidence)}</td></tr>`).join('');
 $('schedule-state').textContent=s.schedule?.status?`scheduled launch: ${s.schedule.status}${s.schedule.at?' · '+new Date(s.schedule.at*1000).toLocaleString():''}${s.schedule.error?' · '+s.schedule.error:''}`:'no scheduled launch';
 }catch(e){$('control-task').textContent=e.message}}
async function action(name,data={}){try{const r=await fetch('/control/'+name,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const s=await r.json();if(!r.ok)throw Error(s.error);$('control-task').textContent=s.message||'request accepted';await refresh()}catch(e){$('control-task').textContent=e.message}}
$('fleet-sync').onclick=()=>action('sync');$('brain-train').onclick=()=>action('train');$('fleet-launch').onclick=()=>action('launch',{workers:+$('fleet-size').value,duration:+$('fleet-duration').value});
$('fleet-schedule').onclick=()=>action('schedule',{workers:+$('fleet-size').value,duration:+$('fleet-duration').value,at:new Date($('schedule-at').value).getTime()/1000});$('fleet-unschedule').onclick=()=>action('unschedule');
ready=refresh();setInterval(refresh,5000);
})();
