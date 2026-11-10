/* Local account sessions: credentials stay in HttpOnly cookies; CSRF nonce stays in memory. */
window.PriceTrackAuth = (() => {
 const nativeFetch=window.fetch.bind(window);let current=null,csrf='',locked=false;
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const can=permission=>Boolean(current?.permissions.includes(permission));
 function showLogin(message=''){
  current=null;csrf='';document.body.classList.add('auth-locked');document.getElementById('main')?.replaceChildren();
  let gate=document.getElementById('auth-gate');if(gate)gate.remove();gate=document.createElement('section');gate.id='auth-gate';gate.className='auth-gate';
  gate.innerHTML=`<form class="auth-card"><span class="eyebrow">ProjectTrack · Price Track</span><h1>Sign in</h1><p>Use your configured local account.</p><label class="field">User ID<input name="user_id" autocomplete="username" maxlength="100" required placeholder="Your assigned user ID"></label><label class="field">Password<input name="password" type="password" autocomplete="current-password" maxlength="128" required></label><button class="btn primary" type="submit">Sign in</button><p role="status" class="error-text">${esc(message)}</p><p class="note">Use the credentials supplied by your workspace operator. Company SSO is pending.</p></form>`;
  document.body.appendChild(gate);
  gate.querySelector('form').addEventListener('submit',async event=>{
   event.preventDefault();const form=event.target,button=form.querySelector('button'),status=form.querySelector('[role="status"]');button.disabled=true;status.textContent='Signing in…';
   try{const response=await nativeFetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json','X-PriceTrack-Request':'1'},credentials:'same-origin',body:JSON.stringify({user_id:form.elements.user_id.value.trim(),password:form.elements.password.value})});const data=await response.json();if(!response.ok)throw new Error(data.error?.message||'Sign-in failed.');form.elements.password.value='';window.history.replaceState(null,'',window.location.pathname+(data.user.role==='Admin'?'#/admin/overview':'#/overview'));window.location.reload();}
   catch(error){status.textContent=error.message;form.elements.password.value='';button.disabled=false;}
  });
 }
 window.fetch=async(input,options={})=>{
  const url=new URL(typeof input==='string'?input:input.url,window.location.href);
  if(url.origin!==window.location.origin||!url.pathname.startsWith('/api/'))return nativeFetch(input,options);
  const headers=new Headers(options.headers||(typeof input==='object'?input.headers:undefined));const method=(options.method||(typeof input==='object'?input.method:'GET')||'GET').toUpperCase();
  if(!['GET','HEAD','OPTIONS'].includes(method)&&csrf)headers.set('X-CSRF-Token',csrf);
  const response=await nativeFetch(input,{...options,credentials:'same-origin',headers});
  if(response.status===401&&current&&!locked){locked=true;showLogin('Your session ended. Sign in again.');}
  return response;
 };
 function applyPermissions(){
  if(!current)return;
  const disable=selector=>document.querySelectorAll(selector).forEach(control=>{control.disabled=true;control.title='Your signed-in role has read-only access to this action.';});
  if(!can('resources'))disable('#resource-plan input,#resource-plan select,#resource-plan [data-rp-action]:not([data-rp-action="reload"])');
  if(!can('calculate'))disable('#workbook-calculator input,#workbook-calculator select,#workbook-calculator [data-wc-action]:not([data-wc-action="reload"])');
  if(!can('version'))disable('#save-pricing-version');
  if(!can('create'))disable('[data-action="request-pricing"],[data-action="create-pricing-case"]');
 }
 function showAccount(){
  let box=document.getElementById('signed-in-account');box?.remove();box=document.createElement('div');box.id='signed-in-account';box.className='auth-account';box.innerHTML=`<section class="auth-card"><h2>Signed in</h2><p>${esc(current.display_name)}<br>${esc(current.user_id)} · ${esc(current.role)}</p><p class="note">Role actions and explicit opportunity scopes are checked by the backend. Approval policy is still the illustrative local route.</p><div class="actions"><button class="btn" data-account-close>Close</button><button class="btn primary" data-account-logout>Sign out</button></div><p role="status"></p></section>`;document.body.appendChild(box);
  box.querySelector('[data-account-close]').onclick=()=>box.remove();box.querySelector('[data-account-logout]').onclick=async event=>{event.target.disabled=true;try{const response=await window.fetch('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!response.ok&&response.status!==401)throw new Error('Could not sign out; try again.');box.remove();showLogin('You have signed out.');window.history.replaceState(null,'',window.location.pathname);window.location.reload();}catch(error){box.querySelector('[role="status"]').textContent=error.message;event.target.disabled=false;}};
 }
 async function adminDirectory(){
  const response=await window.fetch('/api/users'),data=await response.json();if(!response.ok)return '<p>Account directory access is unavailable.</p>';
  return `<section class="panel"><div class="panel-head"><h3>Seeded account directory</h3></div><div class="panel-body"><p class="note">Use manage_users.py from the trusted backend terminal to set passwords, enable/disable accounts and grant opportunity access. Admin does not grant Finance authority or case access.</p></div><div class="table-wrap"><table><thead><tr><th>User ID</th><th>Name</th><th>Role</th><th>Enabled</th></tr></thead><tbody>${data.users.map(user=>`<tr><td>${esc(user.user_id)}</td><td>${esc(user.display_name)}</td><td>${esc(user.role)}</td><td>${user.enabled?'Yes':'No'}</td></tr>`).join('')}</tbody></table></div></section>`;
 }
 const ready=(async()=>{
  try{const response=await nativeFetch('/api/auth/me',{credentials:'same-origin'});if(!response.ok){showLogin(response.status===401?'':'Start both Python servers, then sign in.');return null;}const data=await response.json();current=data.user;csrf=data.csrf_token;document.body.classList.remove('auth-locked');document.querySelector('.profile-copy b').textContent=current.display_name;document.querySelector('.profile-copy small').textContent=current.role;document.querySelector('.profile .avatar').textContent=current.display_name.split(/\s+/).map(word=>word[0]).slice(0,2).join('');new MutationObserver(applyPermissions).observe(document.getElementById('main'),{childList:true,subtree:true});return current;}
  catch{showLogin('Start both Python servers, then reload this page.');return null;}
 })();
 return {ready,get user(){return current;},can,showLogin,showAccount,applyPermissions,adminDirectory};
})();
