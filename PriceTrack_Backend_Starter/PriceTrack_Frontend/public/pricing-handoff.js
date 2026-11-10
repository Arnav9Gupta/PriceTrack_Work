window.PricingHandoff=(()=>{
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 async function request(url,options){const r=await fetch(url,options),d=await r.json();if(!r.ok)throw Error(d.error?.message||'Request failed');return d;}
 async function render(id){
  try{
   const url='/api/pricing-cases/'+encodeURIComponent(id)+'/handoff',d=await request(url),can=PriceTrackAuth.can('negotiate');
   const input=(key,label,type='text')=>`<label class="field">${label}<input name="${key}" type="${type}" maxlength="2000" required></label>`;
   const form=(action,content,label)=>`<form data-action="${action}"><div class="form-grid">${content}</div><button class="btn primary" type="submit">${label}</button></form>`;
   setTimeout(()=>{
    const root=document.getElementById('handoff-content');if(!root||root.dataset.case!==id)return;
    root.querySelectorAll('form').forEach(f=>f.addEventListener('submit',async e=>{
     e.preventDefault();const button=f.querySelector('button');button.disabled=true;
     const payload=Object.fromEntries(new FormData(f));Object.assign(payload,{action:f.dataset.action,version_number:d.versions[0],expected_revision:d.revision,confirm:f.elements.confirm?.checked===true});
     try{await request(url,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const html=await render(id);if(root.isConnected)root.outerHTML=html;}
     catch(error){root.querySelector('[role="status"]').textContent=error.message;button.disabled=false;}
    }));
   },0);
   let controls='';
   if(can&&d.versions.length){
    if(!d.agreement)controls=form('record_agreement',input('client_contact','Client contact / organization')+input('accepted_date','Acceptance date','date')+input('evidence_reference','Evidence reference (email subject, document ID or URL)')+input('note','Acceptance details / scope')+'<label><input name="confirm" type="checkbox" required> I confirm client acceptance was received for V'+d.versions[0]+'.</label>','Record client agreement');
    else{
     controls=form('withdraw_agreement',input('note','Reason for withdrawing agreement'),'Withdraw agreement');
     if(!d.agreement_outdated&&!d.handoff)controls+=form('prepare_handoff',input('delivery_owner','Intended delivery owner / team')+input('handoff_note','Delivery scope, timing and handoff notes'),'Prepare local handoff');
    }
   }
   return `<div id="handoff-content" data-case="${esc(id)}"><div class="callout info"><div><b>Client agreement and project handoff</b><p>Records acceptance reported by your signed-in account. Evidence is a reference only; no document is uploaded or verified.</p><p>Company approval rules are unconfirmed. Handoffs are prepared locally; Project Tracker is not connected and no external project is created.</p></div></div><section class="panel"><div class="panel-body"><p>Latest saved version: ${d.versions.length?'V'+d.versions[0]:'None — save a pricing version first'}</p><p>Agreement: ${d.agreement?'Recorded for V'+d.agreement.version_number:'Not recorded'}${d.agreement_outdated?' — OUTDATED: withdraw and record acceptance for the latest version':''}</p><p>Handoff: ${d.handoff?'Prepared locally for V'+d.handoff.version_number:'Not prepared'}</p>${controls}<p role="status" aria-live="polite"></p></div></section><section class="panel"><div class="panel-head"><h3>Agreement and handoff history</h3></div><div class="panel-body">${d.events.map(e=>`<article><b>${esc(e.action.replaceAll('_',' '))} · V${e.version_number}</b><p>${esc(e.actor)} · ${esc(e.created_at)}</p>${Object.entries(e.details).map(([k,v])=>`<p>${esc(k.replaceAll('_',' '))}: ${esc(v)}</p>`).join('')}</article>`).join('')||'<p>No records yet.</p>'}</div></section></div>`;
  }catch(e){return '<p role="alert">'+esc(e.message)+'</p>';}
 }
 return {render};
})();
