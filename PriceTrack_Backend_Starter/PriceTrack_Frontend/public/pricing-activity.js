window.PricingActivity = (() => {
 const selections=new Map();
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const names={case:'Case',resource:'Resource plan',calculation:'Calculation',version:'Saved version',review:'Demo review',negotiation:'Negotiation'};
 const sections={case:'summary',resource:'estimates',calculation:'calculator',version:'versions',review:'approvals',negotiation:'negotiation'};
 function filtered(events,selection){const rows=events.filter(event=>(!selection.kind||event.kind===selection.kind)&&(!selection.version||String(event.version_number)===selection.version));return selection.order==='oldest'?[...rows].reverse():rows;}
 function markup(events,selection,id){
  const rows=filtered(events,selection);selection.page=Math.max(0,Math.min(selection.page,Math.ceil(rows.length/20)-1));const start=selection.page*20;
  return `<div class="panel-body"><div class="timeline">${rows.slice(start,start+20).map(event=>`<article class="event"><span class="event-dot">•</span><div><div class="timeline-title">${esc(event.title)}${event.version_number?' · V'+event.version_number:''}</div><p class="note">${esc(event.created_at)} · ${esc(event.actor)}</p><span class="badge outline">${esc(event.provenance)}</span><p class="review-comment">${esc(event.detail||'')}</p><a href="#/cases/${encodeURIComponent(id)}/${sections[event.kind]||'summary'}">Open ${esc(names[event.kind]||'case')}</a></div></article>`).join('')||'<p>No activity matches these filters.</p>'}</div></div><div class="panel-foot"><span>${rows.length?start+1:0}–${Math.min(start+20,rows.length)} of ${rows.length} events</span><div class="actions"><button class="btn small" data-activity-page="-1" ${selection.page===0?'disabled':''}>Previous</button><button class="btn small" data-activity-page="1" ${start+20>=rows.length?'disabled':''}>Next</button></div></div>`;
 }
 async function render(id){
  try{
   const response=await fetch('/api/pricing-cases/'+encodeURIComponent(id)+'/activity');const data=await response.json();if(!response.ok)throw new Error(data.error?.message||data.error||'Could not load activity');
   if(!selections.has(id))selections.set(id,{kind:'',version:'',order:'newest',page:0});const selection=selections.get(id);
   setTimeout(()=>{
    const root=document.getElementById('case-activity');if(!root||root.dataset.case!==id)return;
    const draw=()=>{root.querySelector('[data-activity-events]').innerHTML=markup(data.events,selection,id);};
    root.querySelectorAll('[data-activity-filter]').forEach(input=>input.addEventListener('change',()=>{selection[input.dataset.activityFilter]=input.value;selection.page=0;draw();}));
    root.addEventListener('click',async event=>{
     const page=event.target.closest('[data-activity-page]');if(page&&!page.disabled){selection.page+=Number(page.dataset.activityPage);draw();return;}
     const reload=event.target.closest('[data-activity-reload]');if(reload){reload.disabled=true;const html=await render(id);if(root.isConnected)root.outerHTML=html;}
    });
   },0);
   const option=(value,label,selected)=>`<option value="${esc(value)}" ${value===selected?'selected':''}>${esc(label)}</option>`;
   const versions=[...new Set(data.events.map(event=>event.version_number).filter(Boolean))].sort((a,b)=>b-a);
   return `<div id="case-activity" data-case="${esc(id)}"><div class="callout info"><span>${esc(data.note)}</span></div><section class="panel"><div class="panel-head"><h3>Saved case activity · ${data.total} events</h3><button class="btn" data-activity-reload>Reload activity</button></div><div class="toolbar dashboard-filters"><label class="field">Activity type<select data-activity-filter="kind">${option('','All types',selection.kind)}${Object.entries(names).map(([key,label])=>option(key,label,selection.kind)).join('')}</select></label><label class="field">Saved version<select data-activity-filter="version">${option('','All versions and draft events',selection.version)}${versions.map(number=>option(String(number),'V'+number,selection.version)).join('')}</select></label><label class="field">Order<select data-activity-filter="order">${option('newest','Newest first',selection.order)}${option('oldest','Oldest first',selection.order)}</select></label></div><div class="panel-body"><p class="note">The version filter shows events explicitly linked to that saved version. Resource and calculation draft events have no version label. Existing records are shown once alongside newly recorded events.</p></div><div data-activity-events>${markup(data.events,selection,id)}</div></section></div>`;
  }catch(error){return '<section class="panel"><div class="panel-body"><p role="alert">Activity unavailable: '+esc(error.message)+'</p></div></section>';}
 }
 return {render,filtered};
})();
