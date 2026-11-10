/* Export a selected immutable snapshot; no calculator or write API is invoked. */
window.PricingExport = (() => {
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const plain=value=>value===null||value===undefined||value===''?'Not entered':String(value);
 const money=value=>PricingComparison.formatMoney(value);
 const pct=value=>PricingComparison.formatPercent(value);
 const disclosure='Local synthetic-data demo. This saved pricing snapshot is not approval evidence or a final client quotation.';
 function sections(record,version){
  const snapshot=version.snapshot,result=snapshot.result||{},inputs=snapshot.inputs||{};
  if(result.currency!=='USD')throw new Error('Export currently supports saved USD workbook results only.');
  const groups=[];
  const add=(title,headers,rows)=>groups.push({title,headers,rows});
  add('Case and saved version',['Field','Value'],[
   ['Case ID',record.case_id],['Account',record.account_name],['Opportunity',record.opportunity_name],['Opportunity ID',record.opportunity_id],['Opportunity owner',record.opportunity_owner],['Source stage',record.opportunity_stage],['Saved version','V'+version.number],['Version saved at',version.created_at],['Calculation revision',version.calculation_revision],['Resource revision',snapshot.resource_revision],['Calculation saved at',snapshot.calculated_at],['Workbook reference SHA256',snapshot.reference_hash]
  ]);
  add('Financial results',['Metric','Saved value'],[['Revenue',money(result.revenue)],['Contribution margin',pct(result.cm)],['Projected gross margin',pct(result.gm)],['Workbook headcount total',result.total_people],['Project vertical',inputs.vertical]]);
  add('Stream results',['Stream','Revenue','CM','Projected GM'],['onshore','offshore'].map(stream=>[stream,money(result.streams?.[stream]?.revenue),pct(result.streams?.[stream]?.cm),pct(result.streams?.[stream]?.gm)]));
  add('Calculator settings',['Setting','Saved value'],[['Bench loading',pct(inputs.bench)],['Onshore target CM',pct(inputs.onshore_cm)],['Offshore target CM',pct(inputs.offshore_cm)],['Onshore hours / month',inputs.onshore_hours],['Offshore hours / month',inputs.offshore_hours],['IP deal revenue',money(inputs.ip_revenue)]]);
  add('Workbook team inputs',['Stream','Role / experience','People','Months','Billability','Effective hours','Revenue'],(inputs.resources||[]).map((row,index)=>[row.stream,result.lines?.[index]?.role||'Workbook role '+row.rate_id,row.people,row.months,pct(row.billability),result.lines?.[index]?.effective_hours,money(result.lines?.[index]?.revenue)]));
  add('IP / product descriptions',['Product','Phase','Module','Quantity'],(inputs.ip||[]).map(row=>[row.product,row.phase,row.module,row.quantity]));
  add('Saved simulations',['Simulation','Target CM','Revenue','Projected GM'],(result.simulations||[]).map((row,index)=>[index+1,pct(row.target_cm),money(row.revenue),pct(row.gm)]));
  const resources=snapshot.resources||[],months=snapshot.months||[];
  add('Saved resource dimensions',['Resource ID','Field','Saved value'],resources.flatMap(row=>['role','capability','secondary','department','location','country','grade'].map(field=>[row.row_id,field,row.fields?.[field]])));
  add('Saved monthly resource hours',['Resource ID','Month','Hours'],resources.flatMap(row=>months.map((month,index)=>[row.row_id,month,row.hours?.[index]])));
  return groups.map(group=>({...group,rows:group.rows.map(row=>row.map(plain))}));
 }
 function html(record,version,generatedAt){
  const groups=sections(record,version);
  return '<!doctype html>'+`<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>Price Track · V${version.number}</title><style>@page{size:A4;margin:14mm}*{box-sizing:border-box}body{font:12px/1.5 'Segoe UI',Arial,sans-serif;color:#17141b;max-width:1050px;margin:32px auto;padding:0 24px}header{border-bottom:3px solid #6800e0;padding-bottom:16px}h1{font-size:27px;margin:4px 0}h2{font-size:17px;margin:28px 0 10px;color:#420897}p{overflow-wrap:anywhere}.label{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#6800e0}.notice{background:#f2ebfc;padding:13px;border-radius:5px}.muted{color:#67616e;font-size:11px}table{width:100%;border-collapse:collapse;table-layout:fixed;margin-bottom:20px}th,td{border:1px solid #ddd6e6;text-align:left;vertical-align:top;padding:7px;overflow-wrap:anywhere;white-space:pre-wrap}th{background:#f5f0fc;font-weight:600}thead{display:table-header-group}tr{break-inside:avoid}footer{margin-top:30px;border-top:1px solid #ddd6e6;padding-top:12px}@media print{body{max-width:none;margin:0;padding:0;font-size:10px}h2{break-after:avoid}th,td{padding:5px}.print-note{display:none}}</style></head><body><header><span class="label">Price Track · Internal pricing review</span><h1>${esc(record.account_name||'Pricing case')} · V${version.number}</h1><p>${esc(record.opportunity_name||record.opportunity_id)}</p><p class="muted">Exported ${esc(generatedAt)} · Snapshot saved ${esc(version.created_at)}</p></header><p class="notice">${esc(disclosure)}</p><p class="print-note">To save as PDF: open this file in your browser, press Ctrl+P, and choose Save as PDF.</p>${groups.map(group=>`<section><h2>${esc(group.title)}</h2>${group.rows.length?`<table><thead><tr>${group.headers.map(header=>'<th>'+esc(header)+'</th>').join('')}</tr></thead><tbody>${group.rows.map(row=>'<tr>'+row.map(cell=>'<td>'+esc(cell)+'</td>').join('')+'</tr>').join('')}</tbody></table>`:'<p class="muted">No entries in this saved version.</p>'}</section>`).join('')}<footer><p class="muted">Financial display values are rounded to two decimals. Values are from this saved version. Current draft edits and negotiation amounts are separate. Raw hourly reference costs, employee CTC and IP unit costs are omitted. Missing values remain unavailable or not entered; blank planned hours are distinct from zero. Simulation GM may be unavailable because the source workbook references empty cells. No calculation or approval is performed by this export.</p><p class="muted">${esc(disclosure)}</p></footer></body></html>`;
 }
 function csvCell(value){
  let text=String(value??'');
  // Protect spreadsheet opening even when quoted cells begin with a formula marker.
  if(/^[\s\u0000-\u001f]*[=+\-@]/.test(text)||/^[\t\r\n]/.test(text))text="'"+text;
  return '"'+text.replace(/"/g,'""')+'"';
 }
 function csv(record,version,generatedAt){
  const rows=[['Price Track saved version export'],[disclosure],['Exported at',generatedAt],['Case ID',record.case_id],['Version','V'+version.number],[]];
  for(const group of sections(record,version)){rows.push([group.title],group.headers,...group.rows,[]);}
  rows.push(['Notes','Raw hourly costs, employee CTC and IP unit costs are omitted. Current draft and negotiation amounts are separate. Export does not approve or finalize pricing.']);
  return '\uFEFF'+rows.map(row=>row.map(csvCell).join(',')).join('\r\n');
 }
 async function load(id,number){
  async function read(url){const response=await fetch(url);const data=await response.json();if(!response.ok)throw new Error(data.error?.message||data.error||'Could not load saved pricing data');return data;}
  const base='/api/pricing-cases';const [cases,history]=await Promise.all([read(base+'?case_id='+encodeURIComponent(id)),read(base+'/'+encodeURIComponent(id)+'/versions')]);
  const record=cases.pricing_cases?.find(row=>row.case_id===id),version=history.versions?.find(row=>row.number===number);
  if(!record||!version)throw new Error('The selected saved pricing version is unavailable.');
  return {record,version};
 }
 let busy=false;
 document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-version-export]');if(!button||button.disabled||busy)return;
  const root=button.closest('#pricing-version-content'),id=root?.dataset.case,number=Number(button.dataset.version),format=button.dataset.versionExport;
  if(!id||!Number.isSafeInteger(number)||!['html','csv'].includes(format))return;
  busy=true;button.disabled=true;const status=root.querySelector('#pricing-version-message');status.textContent='Preparing saved version export…';
  try{
   const {record,version}=await load(id,number),at=new Date().toISOString();
   const content=format==='html'?html(record,version,at):csv(record,version,at);
   const blob=new Blob([content],{type:format==='html'?'text/html;charset=utf-8':'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob);
   try{const anchor=document.createElement('a');anchor.href=url;anchor.download='PriceTrack_'+id.replace(/[^a-zA-Z0-9_-]/g,'').slice(0,70)+'_V'+number+'.'+format;document.body.appendChild(anchor);anchor.click();anchor.remove();}finally{setTimeout(()=>URL.revokeObjectURL(url),1000);}
   status.textContent='Saved V'+number+' export prepared. Check your browser downloads.';
  }catch(error){status.textContent=error.message;}
  finally{busy=false;button.disabled=false;}
 });
 return {html,csv,load};
})();
