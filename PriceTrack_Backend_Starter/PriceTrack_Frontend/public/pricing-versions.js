window.PricingVersions = (() => {
 const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 async function request(url,options){const r=await fetch(url,options);const data=await r.json();if(!r.ok)throw new Error(data.error?.message||'Request failed');return data;}
 async function render(id){
  try {
   const base='/api/pricing-cases/'+encodeURIComponent(id);
   const [history,draft]=await Promise.all([request(base+'/versions'),request(base+'/workbook-calculation')]);
   setTimeout(()=>{const button=document.getElementById('save-pricing-version');if(button)button.onclick=async()=>{
    button.disabled=true;
    try{await request(base+'/versions',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:draft.revision})});document.getElementById('pricing-version-content').outerHTML=await render(id);}
    catch(error){document.getElementById('pricing-version-message').textContent=error.message;button.disabled=false;}
   };},0);
   return `<section class="panel" id="pricing-version-content" data-case="${escape(id)}"><div class="panel-body"><h3>Pricing snapshots</h3><p>Save the last calculated backend draft as V1, V2 and later versions. Earlier snapshots remain available after draft edits. Open the Approvals tab to request a local demo review for a saved version. Company approval policy remains pending.</p><p>Calculation revision: ${draft.revision||'None'} ${draft.stale?' · Outdated — recalculate first':''}</p><button class="btn primary" id="save-pricing-version" ${!draft.result||draft.stale?'disabled':''}>Save calculated draft as version</button><a class="btn" href="#/cases/${encodeURIComponent(id)}/compare">Compare saved versions</a><p id="pricing-version-message" role="status"></p>${history.versions.length?history.versions.map(v=>`<details class="top-space"><summary>V${v.number} · ${escape(v.created_at)} · Draft snapshot</summary><p>Calculation revision ${v.calculation_revision} · Resource revision ${v.snapshot.resource_revision}</p><div class="actions"><button type="button" class="btn" data-version-export="html" data-version="${v.number}">Download printable summary</button><button type="button" class="btn" data-version-export="csv" data-version="${v.number}">Download CSV</button></div><h4>Saved results</h4><pre style="white-space:pre-wrap">${escape(JSON.stringify(v.snapshot.result,null,2))}</pre><h4>Saved calculator inputs</h4><pre style="white-space:pre-wrap">${escape(JSON.stringify(v.snapshot.inputs,null,2))}</pre></details>`).join(''):'<p>No saved versions yet. Calculate and save a draft in the workbook calculator first.</p>'}</div></section>`;
  }catch(error){return '<p role="alert">'+escape(error.message)+'</p>';}
 }
 return {render};
})();
