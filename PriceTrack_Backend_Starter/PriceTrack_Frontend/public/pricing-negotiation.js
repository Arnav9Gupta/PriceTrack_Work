window.PricingNegotiation = (() => {
 const drafts=new Map();
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const money=value=>value==null?'No amount recorded':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(value));
 async function request(url,options){const response=await fetch(url,options);const data=await response.json();if(!response.ok)throw new Error(data.error?.message||data.error||'Request failed');return data;}
 function dirty(draft){return Boolean(draft?.note.trim()||draft?.amount.trim());}
 window.addEventListener('beforeunload',event=>{if([...drafts.values()].some(dirty)){event.preventDefault();event.returnValue='';}});
 function events(data,filter){const list=data.events.filter(event=>!filter||String(event.version_number)===filter);return list.length?'<div class="timeline">'+list.map(event=>`<div class="event"><span class="event-dot">•</span><div><div class="timeline-title">${esc(event.kind)} · V${event.version_number}${event.amount_usd!=null?' · '+money(event.amount_usd):''}</div><small>${esc(event.actor_name)} · ${esc(event.actor_role)} · ${esc(event.created_at)}</small><p class="review-comment">${esc(event.note)}</p></div></div>`).join('')+'</div>':'<p>No negotiation entries for this selection.</p>';}
 async function render(id){
  try{
   const base='/api/pricing-cases/'+encodeURIComponent(id)+'/negotiation';const data=await request(base);
   if(!drafts.has(id))drafts.set(id,{version:String(data.versions[0]?.number||''),actor:data.actors.find(actor=>actor.role==='Pricing Analyst')?.user_id||data.actors[0]?.user_id||'',kind:'Client Ask',amount:'',note:'',filter:''});
   const draft=drafts.get(id);draft.actor=data.current_user.user_id;const options=(values,selected)=>values.map(([value,label])=>`<option value="${esc(value)}" ${String(value)===selected?'selected':''}>${esc(label)}</option>`).join('');
   setTimeout(()=>{
    const root=document.getElementById('negotiation-content');if(!root||root.dataset.case!==id)return;
    const form=root.querySelector('form');let busy=false;
    const update=()=>{root.querySelectorAll('[data-neg-field]').forEach(input=>draft[input.dataset.negField]=input.value);};
    const status=message=>{root.querySelector('[role="status"]').textContent=message;};
    const updateKind=()=>{const input=form?.querySelector('[data-neg-field="amount"]');if(input){const allowed=['Client Ask','Company Offer'].includes(draft.kind);input.disabled=!allowed;if(!allowed){draft.amount='';input.value='';}}};
    const versionNote=()=>{const note=root.querySelector('[data-version-note]');if(note)note.textContent=draft.version!==String(data.versions[0]?.number)?'Recording against a historical version. Choose the version actually discussed.':'Recording against the latest saved version.';};
    root.querySelectorAll('[data-neg-field]').forEach(input=>input.addEventListener('input',()=>{update();updateKind();versionNote();}));
    updateKind();versionNote();
    root.querySelector('[data-history-filter]')?.addEventListener('change',event=>{draft.filter=event.target.value;root.querySelector('[data-neg-events]').innerHTML=events(data,draft.filter);});
    root.querySelector('[data-neg-reload]')?.addEventListener('click',async()=>{
     if(busy)return;
     update();busy=true;
     const html=await render(id);if(root.isConnected)root.outerHTML=html;
    });
    form?.addEventListener('submit',async event=>{
     event.preventDefault();if(busy)return;update();
     if(!draft.note.trim()){status('Enter a discussion note before saving.');return;}
     busy=true;root.querySelectorAll('input,select,textarea,button').forEach(control=>control.disabled=true);
     try{
      await request(base,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:data.revision,version_number:Number(draft.version),kind:draft.kind,amount_usd:draft.amount||null,currency:'USD',note:draft.note})});
      draft.note='';draft.amount='';
      const html=await render(id);if(root.isConnected){root.outerHTML=html;document.getElementById('negotiation-content')?.querySelector('[role="status"]')?.append('Negotiation entry saved to SQLite.');}
     }catch(error){status(error.message);root.querySelectorAll('input,select,textarea,button').forEach(control=>control.disabled=false);updateKind();busy=false;}
    });
   },0);
   const form=data.versions.length&&data.actors.length?`<form><div class="form-grid"><label class="field">Saved pricing version<select data-neg-field="version">${options(data.versions.map(version=>[version.number,'V'+version.number+' · Calculation r'+version.calculation_revision]),draft.version)}</select></label><div class="field">Recorded by<span>${esc(data.current_user.display_name)} · ${esc(data.current_user.role)}</span></div><label class="field">Discussion type<select data-neg-field="kind">${options(data.kinds.map(kind=>[kind,kind]),draft.kind)}</select></label><label class="field">Discussed total amount · USD (optional)<input data-neg-field="amount" type="number" min="0" max="999999999999.99" step="0.01" value="${esc(draft.amount)}" placeholder="For a client ask or company offer"></label><label class="field full">Discussion note / reason<textarea data-neg-field="note" rows="4" maxlength="4000" required placeholder="Describe what was discussed and why.">${esc(draft.note)}</textarea></label></div><p class="note" data-version-note></p><button type="submit" class="btn primary">Save negotiation entry</button></form>`:`<p>${data.versions.length?'Your signed-in role can read this log but cannot add negotiation entries.':'Save a calculated pricing version before recording a negotiation.'}</p><a href="#/cases/${encodeURIComponent(id)}/versions">Open Pricing Versions</a>`;
   return `<div id="negotiation-content" data-case="${esc(id)}"><div class="callout info"><div><b>Record the discussion</b><p>Amounts describe a client ask or company offer. To change calculated pricing, edit the workbook calculator and save a new version for review. Recording an offer does not approve or finalize it.</p><p class="note">The recorder is your signed-in account; backend role and opportunity access checks apply. Entries stay in this database; no message is sent to the client.</p></div></div><section class="panel"><div class="panel-head"><h3>New negotiation entry</h3><button class="btn" data-neg-reload>Reload saved history</button></div><div class="panel-body">${form}<p class="note">Unsaved notes remain while navigating within this tab session. Reload saved history keeps the note you are writing.</p><p role="status" aria-live="polite"></p></div></section><section class="panel"><div class="panel-head"><h3>Saved discussion history · ${data.events.length} entries</h3><label class="field">Version<select data-history-filter><option value="">All versions</option>${options(data.versions.map(version=>[version.number,'V'+version.number]),draft.filter)}</select></label></div><div class="panel-body" data-neg-events>${events(data,draft.filter)}</div></section></div>`;
  }catch(error){return '<p role="alert">'+esc(error.message)+'</p>';}
 }
 return {render};
})();
