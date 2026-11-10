/* Read-only comparison of persisted snapshots. Decimal deltas are display values only. */
window.PricingComparison = (() => {
 const selections=new Map();
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function decimal(value){
  if(value===null||value===undefined||value===''||typeof value==='boolean')return null;
  const match=String(value).match(/^([+-]?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/);if(!match)return null;
  const exponent=Number(match[4]||0);if(Math.abs(exponent)>1000)return null;
  let scale=(match[3]||'').length-exponent,coefficient=BigInt(match[2]+(match[3]||''))*(match[1]==='-'?-1n:1n);
  if(scale<0){coefficient*=10n**BigInt(-scale);scale=0;}
  return {coefficient,scale};
 }
 function minus(before,after){const a=decimal(before),b=decimal(after);if(!a||!b)return null;const scale=Math.max(a.scale,b.scale);return {coefficient:b.coefficient*10n**BigInt(scale-b.scale)-a.coefficient*10n**BigInt(scale-a.scale),scale};}
 function formatted(value,places=2,shift=0,signed=false){
  const n=value&&typeof value==='object'&&'coefficient' in value?value:decimal(value);if(!n)return 'Unavailable';
  const negative=n.coefficient<0n;let digits=negative?-n.coefficient:n.coefficient;
  const excess=n.scale-shift-places;
  if(excess>0){const divisor=10n**BigInt(excess);digits=(digits+divisor/2n)/divisor;}else digits*=10n**BigInt(-excess);
  const raw=digits.toString().padStart(places+1,'0');const whole=(places?raw.slice(0,-places):raw).replace(/\B(?=(\d{3})+(?!\d))/g,',');
  return (digits===0n?'':negative?'−':signed?'+':'')+whole+(places?'.'+raw.slice(-places):'');
 }
 const money=value=>decimal(value)?formatted(value)+' USD':'Unavailable';
 const percentage=value=>decimal(value)?formatted(value,2,2)+'%':'Unavailable';
 const plain=value=>value===null||value===undefined?'Not entered':String(value);
 function same(a,b){const delta=minus(a,b);return delta?delta.coefficient===0n:a===b;}
 function buildComparison(before,after){
  const resultA=before.snapshot.result||{},resultB=after.snapshot.result||{},inputA=before.snapshot.inputs||{},inputB=after.snapshot.inputs||{};
  const metrics=[];
  function metric(label,a,b,kind){metrics.push({label,before:a,after:b,kind,delta:minus(a,b)});}
  metric('Total revenue',resultA.revenue,resultB.revenue,'money');metric('Contribution margin',resultA.cm,resultB.cm,'percent');metric('Projected gross margin',resultA.gm,resultB.gm,'percent');
  for(const stream of ['onshore','offshore']){
   const a=resultA.streams?.[stream]||{},b=resultB.streams?.[stream]||{};
   metric(stream+' revenue',a.revenue,b.revenue,'money');metric(stream+' CM',a.cm,b.cm,'percent');metric(stream+' projected GM',a.gm,b.gm,'percent');
  }
  metric('Workbook headcount total',resultA.total_people,resultB.total_people,'number');
  for(let i=0;i<2;i++)metric('Simulation '+(i+1)+' revenue',resultA.simulations?.[i]?.revenue,resultB.simulations?.[i]?.revenue,'money');
  const changes=[];
  function change(area,field,a,b,format=plain){if(!same(a,b))changes.push({area,field,before:format(a),after:format(b)});}
  for(const [key,label,format] of [['vertical','Project vertical',plain],['bench','Bench loading',percentage],['onshore_cm','Onshore target CM',percentage],['offshore_cm','Offshore target CM',percentage],['onshore_hours','Onshore hours / month',plain],['offshore_hours','Offshore hours / month',plain],['ip_revenue','IP deal revenue',money]])change('Calculator',label,inputA[key],inputB[key],format);
  for(let i=0;i<2;i++)change('Simulation '+(i+1),'Target CM',inputA.simulation_cm?.[i],inputB.simulation_cm?.[i],percentage);
  for(const stream of ['onshore','offshore']){
   const a=(inputA.resources||[]).map((line,index)=>({line,label:resultA.lines?.[index]?.role})).filter(x=>x.line.stream===stream);
   const b=(inputB.resources||[]).map((line,index)=>({line,label:resultB.lines?.[index]?.role})).filter(x=>x.line.stream===stream);
   for(let i=0;i<Math.max(a.length,b.length);i++){
    const area=stream+' workbook line '+(i+1),x=a[i]?.line,y=b[i]?.line;
    if(!x||!y){changes.push({area,field:x?'Removed line':'Added line',before:x?(a[i].label||'Workbook role '+x.rate_id):'—',after:y?(b[i].label||'Workbook role '+y.rate_id):'—'});continue;}
    change(area,'Workbook role / experience',a[i].label||x.rate_id,b[i].label||y.rate_id);
    change(area,'Saved resource label',x.resource_id||'',y.resource_id||'');
    for(const [field,label] of [['people','People'],['months','Months'],['billability','Billability']])change(area,label,x[field],y[field],field==='billability'?percentage:plain);
   }
  }
  const ipsA=inputA.ip||[],ipsB=inputB.ip||[];
  for(let i=0;i<Math.max(ipsA.length,ipsB.length);i++){
   const a=ipsA[i],b=ipsB[i],area='IP / product line '+(i+1);
   if(!a||!b){changes.push({area,field:a?'Removed line':'Added line',before:a?(a.product||'Unnamed product'):'—',after:b?(b.product||'Unnamed product'):'—'});continue;}
   for(const key of ['product','phase','module','quantity'])change(area,key,a[key],b[key]);
   if(!same(a.unit_cost,b.unit_cost))changes.push({area,field:'Unit cost input',before:'Cost value hidden',after:'Changed · cost value hidden'});
  }
  const monthsA=before.snapshot.months||[],monthsB=after.snapshot.months||[];
  change('Resource plan','Planning months',monthsA.join(', '),monthsB.join(', '));
  const resourceA=new Map((before.snapshot.resources||[]).map(row=>[row.row_id,row]));
  const resourceB=new Map((after.snapshot.resources||[]).map(row=>[row.row_id,row]));
  for(const id of new Set([...resourceA.keys(),...resourceB.keys()])){
   const a=resourceA.get(id),b=resourceB.get(id),area='Resource '+id;
   if(!a||!b){changes.push({area,field:a?'Removed resource':'Added resource',before:a?(a.fields?.role||id):'—',after:b?(b.fields?.role||id):'—'});continue;}
   for(const field of ['role','capability','secondary','department','location','country','grade'])change(area,field,a.fields?.[field],b.fields?.[field]);
   const hoursA=new Map(monthsA.map((month,index)=>[month,a.hours?.[index]])),hoursB=new Map(monthsB.map((month,index)=>[month,b.hours?.[index]]));
   for(const month of new Set([...monthsA,...monthsB]))change(area,month+' hours',hoursA.get(month),hoursB.get(month));
  }
  return {metrics,changes,referenceChanged:before.snapshot.reference_hash!==after.snapshot.reference_hash,currencyMismatch:(resultA.currency||'USD')!==(resultB.currency||'USD')};
 }
 function comparison(before,after){
  if(before.number===after.number)return '<p class="panel-body">Select two different versions to compare.</p>';
  const model=buildComparison(before,after);
  if(model.currencyMismatch)return '<p class="panel-body error-text">These versions use different currencies. Comparison requires a confirmed FX policy.</p>';
  const row=metric=>{
   const format=metric.kind==='money'?money:metric.kind==='percent'?percentage:plain;
   const delta=metric.delta===null?'Unavailable':formatted(metric.delta,2,metric.kind==='percent'?2:0,true)+(metric.kind==='money'?' USD':metric.kind==='percent'?' pp':'');
   return `<tr><td>${esc(metric.label)}</td><td>${esc(format(metric.before))}</td><td>${esc(format(metric.after))}</td><td>${esc(delta)}</td></tr>`;
  };
  return `<p class="note panel-body">Change = selected comparison version minus selected baseline. Margin changes use percentage points (pp): 40% → 45% is +5 pp. Display values are rounded to two decimals.</p>${model.referenceChanged?'<div class="callout"><span>The workbook reference snapshot changed between these versions. Consider this when reviewing the differences.</span></div>':''}<section class="panel"><div class="panel-head"><h3>Financial results</h3></div><div class="table-wrap"><table><thead><tr><th>Metric</th><th>Baseline · V${before.number}</th><th>Comparison · V${after.number}</th><th>Change</th></tr></thead><tbody>${model.metrics.map(row).join('')}</tbody></table></div></section><section class="panel"><div class="panel-head"><h3>Input and resource changes · ${model.changes.length}</h3></div><div class="panel-body"><p class="note">Workbook and IP lines are compared by position within their stream; adding a line may shift later positions. Saved resources are matched by resource ID, with hours aligned by month. Blank hours remain distinct from zero.</p></div>${model.changes.length?'<div class="table-wrap"><table><thead><tr><th>Area</th><th>Field</th><th>Baseline</th><th>Comparison</th></tr></thead><tbody>'+model.changes.map(change=>`<tr><td>${esc(change.area)}</td><td>${esc(change.field)}</td><td class="wrap">${esc(change.before)}</td><td class="wrap">${esc(change.after)}</td></tr>`).join('')+'</tbody></table></div>':'<p class="panel-body">No calculator input or resource-plan differences.</p>'}</section>`;
 }
 async function render(id){
  try{
   const response=await fetch('/api/pricing-cases/'+encodeURIComponent(id)+'/versions');const data=await response.json();if(!response.ok)throw new Error(data.error?.message||data.error||'Could not load saved versions');
   const versions=data.versions||[];
   if(versions.length<2)return `<section class="panel"><div class="panel-body"><h3>Two saved versions are needed</h3><p>Save V1, change the calculator inputs, recalculate and save V2. Then return here to compare.</p><a href="#/cases/${encodeURIComponent(id)}/versions">Open Pricing Versions</a></div></section>`;
   const saved=selections.get(id);const pair=saved&&saved.every(number=>versions.some(v=>v.number===number))?saved:[versions[1].number,versions[0].number];selections.set(id,pair);
   const selected=()=>pair.map(number=>versions.find(version=>version.number===number));
   setTimeout(()=>{
    const root=document.getElementById('pricing-comparison');if(!root||root.dataset.case!==id)return;
    const refresh=()=>{const [a,b]=selected();root.querySelector('[data-comparison-output]').innerHTML=comparison(a,b);};
    root.querySelectorAll('[data-compare-select]').forEach(input=>input.addEventListener('change',()=>{pair[Number(input.dataset.compareSelect)]=Number(input.value);refresh();}));
    root.querySelector('[data-compare-swap]').addEventListener('click',()=>{pair.reverse();root.querySelectorAll('[data-compare-select]').forEach(input=>input.value=String(pair[Number(input.dataset.compareSelect)]));refresh();});
   },0);
   const [before,after]=selected();
   return `<div id="pricing-comparison" data-case="${esc(id)}"><div class="callout info"><span>Compare saved snapshots. The working draft is separate. This view does not recalculate pricing or change approval status.</span></div><section class="panel"><div class="panel-body"><div class="actions">${['Baseline version','Comparison version'].map((label,index)=>`<label class="field">${label}<select data-compare-select="${index}">${versions.map(version=>`<option value="${version.number}" ${version.number===pair[index]?'selected':''}>V${version.number} · ${esc(version.created_at)}</option>`).join('')}</select></label>`).join('')}<button class="btn" data-compare-swap>Swap versions</button><a class="btn" href="#/cases/${encodeURIComponent(id)}/versions">Back to versions</a></div></div></section><div data-comparison-output>${comparison(before,after)}</div></div>`;
  }catch(error){return '<p role="alert">'+esc(error.message)+'</p>';}
 }
 return {render,buildComparison,formatMoney:money,formatPercent:percentage};
})();
