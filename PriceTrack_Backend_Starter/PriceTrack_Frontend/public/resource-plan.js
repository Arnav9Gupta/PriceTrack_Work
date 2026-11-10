/* Database-backed resource drafts for source-linked cases. No pricing formulas. */
'use strict';
window.ResourcePlan = (() => {
  const cache = new Map();
  const fields = ['role','capability','secondary','department','location','country','grade'];
  const labels = ['Role','Primary capability','Secondary capability','Department','Location','Country','Grade'];
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const endpoint = id => '/api/pricing-cases/'+encodeURIComponent(id)+'/resources';
  const root = id => {const el=document.querySelector('#resource-plan');return el?.dataset.caseid===id?el:null;};
  async function request(id, options={}) {
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
    try {
      const response=await fetch(endpoint(id),{...options,signal:controller.signal,headers:{'Content-Type':'application/json',...(options.headers||{})}});
      const data=await response.json();
      if(!response.ok)throw new Error(data.error?.message||data.error||`Request failed (${response.status})`);
      return data;
    } finally {clearTimeout(timer);}
  }
  const button = (text, action, extra='', primary=false) => `<button type="button" class="btn ${primary?'primary':''}" data-rp-action="${action}" ${extra}>${text}</button>`;
  const sum = values => values.some(v=>v===null)?'Incomplete':String(Math.round(values.reduce((a,b)=>a+b,0)*100)/100);
  const monthLabel = month => new Intl.DateTimeFormat('en',{year:'numeric',month:'short',timeZone:'UTC'}).format(new Date(month+'-01T00:00:00Z'));
  function markup(id) {
    const item=cache.get(id);
    if(!item)return `<div id="resource-plan" data-caseid="${escape(id)}" class="panel"><div class="panel-body"><p class="error-text">Could not load the saved resource plan. No empty plan has replaced your saved data.</p>${button('Retry loading','reload')}</div></div>`;
    const p=item.plan;
    const rows=p.resources.map((r,i)=>`<tr><td class="sticky"><input aria-label="Resource ${i+1} role" data-rp-field="role" data-row="${i}" value="${escape(r.role)}" maxlength="200" placeholder="Role"></td>${fields.slice(1).map(f=>`<td><input aria-label="Resource ${i+1} ${f}" data-rp-field="${f}" data-row="${i}" value="${escape(r[f])}" maxlength="200" placeholder="${escape(labels[fields.indexOf(f)])}" style="min-width:125px;width:145px;text-align:left"></td>`).join('')}${p.months.map((m,j)=>`<td><input aria-label="Resource ${i+1} ${m} planned hours" type="number" min="0" max="10000" step="any" data-rp-hour="${j}" data-row="${i}" value="${r.hours[j]===null?'':r.hours[j]}" placeholder="—"></td>`).join('')}<td class="numeric" data-rp-total="${i}">${sum(r.hours)}</td><td>${button('Remove','remove',`data-row="${i}"`)}</td></tr>`).join('');
    return `<div id="resource-plan" data-caseid="${escape(id)}"><div class="callout info"><span>Saved resource draft · SQLite. Blank hours mean missing input; 0 is explicit zero. Saving creates a draft revision, not a submitted pricing version or approval.</span></div><section class="panel"><div class="panel-head"><div><h2>Resource estimates & monthly hours</h2><p id="rp-state">${item.dirty?'Unsaved changes':'Saved database state'} · revision ${p.revision} · ${p.updated_at?escape(p.updated_at):'Not saved yet'}</p></div><span class="badge amber">Tech COE / BU review not implemented</span></div><div class="toolbar"><label class="small">Start month <input type="month" id="rp-start" aria-label="Planning start month" value="${escape(p.months[0]||'')}" min="1000-01" max="9999-12"></label><label class="small">Months <input type="number" id="rp-count" aria-label="Number of planning months" min="1" max="24" value="${p.months.length||3}" style="width:68px"></label>${button('Apply months','months')}<span class="spacer"></span>${button('Add resource','add')}${button('Reload saved','reload')}${button('Save resource draft','save','',true)}</div><p class="note panel-body" style="margin:0;padding:12px 19px">Choose your planning period explicitly. Role, primary capability, location, country and grade are needed before future validation; incomplete inputs can be saved as draft.</p>${p.months.length?`<div class="table-wrap"><table class="resource-grid"><thead><tr><th class="sticky">Role</th>${labels.slice(1).map(l=>`<th>${escape(l)}</th>`).join('')}${p.months.map(m=>`<th>${monthLabel(m)}</th>`).join('')}<th>Total hours</th><th>Action</th></tr></thead><tbody>${rows||`<tr><td colspan="${9+p.months.length}" class="empty">No resources yet. Add a row to begin.</td></tr>`}</tbody><tfoot><tr><td class="sticky">Planned hours</td><td colspan="6">${p.resources.length} resource rows</td>${p.months.map((m,j)=>`<td class="numeric" data-rp-month-total="${j}">${sum(p.resources.map(r=>r.hours[j]))}</td>`).join('')}<td class="numeric" id="rp-grand-total">${sum(p.resources.flatMap(r=>r.hours))}</td><td></td></tr></tfoot></table></div>`:'<div class="empty"><b>Choose the start month to begin</b><p>The app does not assume project dates or a standard monthly-hour conversion.</p></div>'}<div class="panel-foot"><span id="rp-message" role="status">${escape(item.message||'Hours are estimates. No rate, cost, FTE or financial output is calculated here.')}</span></div></section></div>`;
  }
  function draw(id) {const el=root(id);if(el)el.outerHTML=markup(id);}
  function dirty(item) {item.dirty=true;item.message='Unsaved resource inputs · Review required';}
  function updateTotals(id) {
    const el=root(id),item=cache.get(id);if(!el||!item)return;
    el.querySelectorAll('[data-rp-total]').forEach(n=>n.textContent=sum(item.plan.resources[Number(n.dataset.rpTotal)].hours));
    el.querySelectorAll('[data-rp-month-total]').forEach(n=>n.textContent=sum(item.plan.resources.map(r=>r.hours[Number(n.dataset.rpMonthTotal)])));
    const total=el.querySelector('#rp-grand-total');if(total)total.textContent=sum(item.plan.resources.flatMap(r=>r.hours));
    el.querySelector('#rp-state').textContent=`Unsaved changes · saved revision ${item.plan.revision}`;
  }
  async function render(id) {
    if(!cache.has(id)) {
      try {cache.set(id,{plan:await request(id),dirty:false,message:''});}
      catch(error) {return markup(id).replace('Could not load the saved resource plan.',`Could not load the saved resource plan: ${escape(error.message)}.`);}
    }
    const html=markup(id);
    return cache.get(id)?.busy?html.replace(/<(input|button)\b/g,'<$1 disabled'):html;
  }
  document.addEventListener('input',event=>{
    const el=event.target,container=el.closest('#resource-plan');if(!container)return;
    const item=cache.get(container.dataset.caseid);if(!item||item.busy)return;
    if(el.hasAttribute('data-rp-field')) {item.plan.resources[Number(el.dataset.row)][el.dataset.rpField]=el.value;dirty(item);updateTotals(container.dataset.caseid);}
    if(el.hasAttribute('data-rp-hour')) {
      // Keep invalid intermediate text in the input; Save checks native validity.
      if(!el.validity.valid){dirty(item);return;}
      item.plan.resources[Number(el.dataset.row)].hours[Number(el.dataset.rpHour)]=el.value===''?null:Number(el.value);
      dirty(item);updateTotals(container.dataset.caseid);
    }
  });
  document.addEventListener('click',async event=>{
    const el=event.target.closest('[data-rp-action]');if(!el||el.disabled)return;
    const container=el.closest('#resource-plan');if(!container)return;
    const id=container.dataset.caseid,action=el.dataset.rpAction,item=cache.get(id);
    if(item?.busy)return;
    try {
      if(action==='reload') {
        if(item?.dirty&&!confirm('Reload the database draft and discard unsaved resource edits?'))return;
        const plan=await request(id);cache.set(id,{plan,dirty:false,message:'Loaded the saved database draft.'});draw(id);return;
      }
      if(!item)return;
      const p=item.plan;
      if(action==='months') {
        const start=container.querySelector('#rp-start'),countInput=container.querySelector('#rp-count');
        if(!start.value||!start.reportValidity()||!countInput.reportValidity())return;
        const count=Number(countInput.value);if(!Number.isInteger(count)||count<1||count>24)throw new Error('Choose 1 to 24 months.');
        let [y,m]=start.value.split('-').map(Number);const months=[];
        for(let i=0;i<count;i++){const year=y+Math.floor((m-1+i)/12);if(year>9999)throw new Error('Planning period exceeds year 9999.');months.push(`${year}-${String((m-1+i)%12+1).padStart(2,'0')}`);}
        const dropped=p.months.some((old,j)=>!months.includes(old)&&p.resources.some(r=>r.hours[j]!==null));
        if(dropped&&!confirm('This period removes months containing hours. Remove those values from the draft?'))return;
        p.resources.forEach(r=>r.hours=months.map(month=>p.months.includes(month)?r.hours[p.months.indexOf(month)]:null));p.months=months;dirty(item);draw(id);
      }
      if(action==='add') {
        if(!p.months.length)throw new Error('Choose and apply the planning months first.');
        if(p.resources.length>=100)throw new Error('This draft supports up to 100 rows.');
        p.resources.push({id:crypto.randomUUID(),...Object.fromEntries(fields.map(f=>[f,''])),hours:p.months.map(()=>null)});dirty(item);draw(id);
      }
      if(action==='remove'&&confirm('Remove this resource row from the draft?')) {p.resources.splice(Number(el.dataset.row),1);dirty(item);draw(id);}
      if(action==='save') {
        const invalid=container.querySelector('input:invalid');if(invalid){invalid.reportValidity();return;}
        if(!p.months.length)throw new Error('Choose and apply the planning months first.');
        if(container.querySelector('#rp-start').value!==p.months[0]||Number(container.querySelector('#rp-count').value)!==p.months.length)throw new Error('Click Apply months before saving a changed planning period.');
        item.busy=true;container.querySelectorAll('input,button').forEach(n=>n.disabled=true);
        const result=await request(id,{method:'PUT',body:JSON.stringify({expected_revision:p.revision,months:p.months,resources:p.resources})});
        cache.set(id,{plan:result,dirty:false,message:`Resource draft revision ${result.revision} saved in SQLite. Refreshing or restarting the app will retain it.`});draw(id);
      }
    } catch(error) {
      if(item)item.message=error.message;
      const message=root(id)?.querySelector('#rp-message');if(message){message.textContent=error.message;message.classList.add('error-text');}
      else alert(error.message);
    } finally {
      if(item)item.busy=false;
      root(id)?.querySelectorAll('input,button').forEach(n=>n.disabled=false);
    }
  });
  window.addEventListener('beforeunload',event=>{if([...cache.values()].some(item=>item.dirty)){event.preventDefault();event.returnValue='';}});
  return {render};
})();
