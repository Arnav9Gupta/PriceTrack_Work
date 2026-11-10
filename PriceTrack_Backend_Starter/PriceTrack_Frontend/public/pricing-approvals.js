window.PricingApprovals = (() => {
 const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const amount = value => value == null ? 'Unavailable' : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(value));
 const percent = value => value == null ? 'Unavailable' : (Number(value)*100).toFixed(2)+'%';
 let actorId='DEMO-Pricing-Analyst';
 async function request(url,options){const response=await fetch(url,options);const data=await response.json();if(!response.ok)throw new Error(data.error?.message||data.error||'Request failed');return data;}
 const note = '<div class="callout info"><div><b>Local approval demo</b><p>Signed-in accounts review the illustrative BU Head → Finance route. The backend enforces role and opportunity access. Company production approval policy remains pending. No notifications are sent.</p></div></div>';
 function eventList(events){return events.length?'<div class="timeline">'+events.map(event=>`<div class="event"><span class="event-dot">•</span><div><div class="timeline-title">V${event.version_number} · ${esc({submit:'Review requested',approve:'Approved step',reject:'Rejected',request_changes:'Changes requested'}[event.action])}</div><small>${esc(event.actor_name)} · ${esc(event.actor_role)} · ${esc(event.created_at)}</small><p class="review-comment">${esc(event.comment||'No submission note')}</p></div></div>`).join('')+'</div>':'<p>No review activity recorded yet.</p>';}
 function card(version,data,id){
  const actor=data.actors.find(user=>user.user_id===actorId);
  const latest=version.number===data.versions[0]?.number;
  const canSubmit=latest&&version.status==='Not requested'&&actor?.role==='Pricing Analyst'&&data.route_available;
  const canDecide=version.status==='Pending'&&version.waiting_on===actor?.role&&data.route_available;
  const status=version.status==='Pending'?'Waiting on '+version.waiting_on:version.status;
  return `<section class="panel"><div class="panel-head"><h3>V${version.number}</h3><span class="badge ${version.status==='Approved in demo'?'green':'outline'}">${esc(status)}</span></div><div class="panel-body"><p class="note">Saved calculation r${version.calculation_revision} · ${esc(version.created_at)}${latest?' · Latest saved version':' · Historical version'}</p><dl class="detail-list"><div><dt>Revenue · USD</dt><dd>${amount(version.result.revenue)}</dd></div><div><dt>Contribution margin</dt><dd>${percent(version.result.cm)}</dd></div><div><dt>Projected gross margin</dt><dd>${percent(version.result.gm)}</dd></div></dl><p class="note">The review covers this saved snapshot. Approval of V${version.number} does not approve another version or the current working draft.</p><a href="#/cases/${encodeURIComponent(id)}/versions">Review saved inputs and results</a>${canSubmit||canDecide?`<label class="field top-space">${canDecide?'Decision reason (required)':'Request note (optional)'}<textarea data-review-comment="${version.number}" maxlength="2000" rows="3"></textarea></label><div class="actions top-space">${canSubmit?`<button class="btn primary" data-review-action="submit" data-version="${version.number}">Request demo review of V${version.number}</button>`:`<button class="btn primary" data-review-action="approve" data-version="${version.number}">Approve V${version.number} step</button><button class="btn" data-review-action="request_changes" data-version="${version.number}">Request changes</button><button class="btn danger" data-review-action="reject" data-version="${version.number}">Reject V${version.number}</button>`}</div>`:`<p class="note">${version.status==='Pending'?'This review step is assigned to a different role.':version.status==='Not requested'?(latest?'A signed-in Pricing Analyst can request review.':'Only the latest saved version can be submitted.'):'This review is closed. Changes require a new calculated version.'}</p>`}</div></section>`;
 }
 async function render(id,activityOnly=false){
  try{
   const base='/api/pricing-cases/'+encodeURIComponent(id)+'/approvals';
   const data=await request(base);actorId=data.current_user.user_id;
   setTimeout(()=>{
    const root=document.getElementById('saved-review-content');if(!root||root.dataset.case!==id)return;
    async function reload(){const html=await render(id,activityOnly);if(root.isConnected)root.outerHTML=html;}
    root.querySelector('[data-review-reload]')?.addEventListener('click',()=>{
     if([...root.querySelectorAll('textarea')].some(input=>input.value.trim())&&!window.confirm('Discard your unsaved review note and reload?'))return;
     reload();
    });
    root.querySelectorAll('[data-review-action]').forEach(button=>button.addEventListener('click',async()=>{
     const comment=root.querySelector(`[data-review-comment="${button.dataset.version}"]`).value.trim();
     if(button.dataset.reviewAction!=='submit'&&!comment){root.querySelector('[role="status"]').textContent='Enter a reason for your decision.';return;}
     root.querySelectorAll('button,select,textarea').forEach(control=>control.disabled=true);
     try{await request(base,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:data.revision,version_number:Number(button.dataset.version),action:button.dataset.reviewAction,comment})});await reload();}
     catch(error){root.querySelector('[role="status"]').textContent=error.message;root.querySelectorAll('button,select,textarea').forEach(control=>control.disabled=false);}
    }));
   },0);
   return `<div id="saved-review-content" data-case="${esc(id)}">${note}${!data.route_available?'<p class="error-text">Illustrative route missing from the imported configuration. Review actions are blocked.</p>':''}<div class="panel"><div class="panel-body"><div class="actions"><span>Signed in as ${esc(data.current_user.display_name)} · ${esc(data.current_user.role)}</span><button class="btn" data-review-reload>Reload reviews</button></div><p role="status" class="error-text" aria-live="polite"></p></div></div>${activityOnly?'':data.versions.length?data.versions.map(version=>card(version,data,id)).join(''):`<div class="panel"><div class="panel-body"><p>Save a calculated pricing version first, then request its review.</p><a href="#/cases/${encodeURIComponent(id)}/versions">Open Pricing Versions</a></div></div>`}<section class="panel"><div class="panel-head"><h3>Review activity · saved in SQLite</h3></div><div class="panel-body">${eventList(data.events)}</div></section></div>`;
  }catch(error){return '<p role="alert">'+esc(error.message)+'</p>';}
 }
 async function inbox(){
  try{const data=await request('/api/approval-inbox');return note+`<section class="panel"><div class="panel-head"><h3>Saved version reviews</h3></div>${data.items.length?'<div class="table-wrap"><table><thead><tr><th>Account / case</th><th>Version</th><th>Status</th><th>Waiting on</th><th>Action</th></tr></thead><tbody>'+data.items.map(item=>`<tr><td>${esc(item.account_name)}<small>${esc(item.case_id)}</small></td><td>V${item.version_number}</td><td>${esc(item.status)}</td><td>${esc(item.waiting_on||'—')}</td><td><a href="#/cases/${encodeURIComponent(item.case_id)}/approvals">Open review</a></td></tr>`).join('')+'</tbody></table></div>':'<div class="panel-body"><p>No reviews requested yet. Open a saved case → Pricing Versions to save a snapshot, then open Approvals.</p></div>'}</section>`;}catch(error){return '<p role="alert">'+esc(error.message)+'</p>';}
 }
 return {render,inbox};
})();
