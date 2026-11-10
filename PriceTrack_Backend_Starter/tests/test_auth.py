import sys,sqlite3,tempfile,threading,json,copy,hashlib,time,os
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
PROJECT_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT_ROOT))
import server,run_frontend,pricing_auth as auth,resource_plan,margin_calculator as mc
server.PriceTrackHandler.log_message=lambda *args:None
run_frontend.Handler.log_message=lambda *args:None
from pricing_activity import timeline
folder=Path(tempfile.mkdtemp());database=folder/'test.sqlite';server.DATABASE_PATH=database
with sqlite3.connect(database) as db:
 db.execute('CREATE TABLE users(user_id TEXT PRIMARY KEY,display_name TEXT,role TEXT,enabled INTEGER,cost_access INTEGER)')
 users=[('CP-1','Owner One','Client Partner',1,0),('CP-2','Owner Two','Client Partner',1,0),('DEMO-Pricing-Analyst','Maya Demo','Pricing Analyst',1,0),('DEMO-BU-Head','Evan Demo','BU Head',1,0),('DEMO-Finance','Priya Demo','Finance',1,1),('ADMIN','Admin User','Admin',1,0),('TECH','Tech User','Tech COE',1,0),('NONE','No Grant','Pricing Analyst',1,0)]
 db.executemany('INSERT INTO users VALUES(?,?,?,?,?)',users)
 db.execute('CREATE TABLE user_opportunity_scope(user_id TEXT,opportunity_id TEXT)')
 db.executemany('INSERT INTO user_opportunity_scope VALUES(?,?)',[('CP-1','OP1'),('CP-2','OP2')])
 db.execute('CREATE TABLE salesforce_opportunities(opportunity_id TEXT PRIMARY KEY,account_id TEXT,account_name TEXT,opportunity_name TEXT,stage TEXT,opportunity_type TEXT,type TEXT,opportunity_owner TEXT,amount TEXT)')
 db.executemany('INSERT INTO salesforce_opportunities VALUES(?,?,?,?,?,?,?,?,?)',[('OP1','ACC1','Account One','Deal One','Needs','MMM','New Business','Owner One','USD 100'),('OP2','ACC2','Account Two','Deal Two','Other','MMM','New Business','Owner Two','USD 200')])
 db.execute('CREATE TABLE workflow_config(config_id INTEGER PRIMARY KEY,setting_group TEXT,source_value TEXT,application_value TEXT,status TEXT,note TEXT)')
 db.execute("INSERT INTO workflow_config VALUES(1,'Approval route','Demo sequential','BU Head > Finance','Illustrative demo only','No production policy')")
 db.execute('CREATE TABLE client_rates(rate_id TEXT,account_id TEXT,role TEXT,selling_rate REAL)')
 db.executemany('INSERT INTO client_rates VALUES(?,?,?,?)',[('RATE1','ACC1','Engineer',100),('RATE2','ACC2','Engineer',200)])
auth.initialize(database);server.initialize_pricing_cases();resource_plan.initialize(database);mc.initialize(database);server.initialize_versions(database);server.initialize_approvals(database);server.initialize_negotiation(database)
password='Testing-only-passphrase!42'
for user in users:auth.set_password(database,user[0],password)
with sqlite3.connect(database) as db:
 db.executemany('INSERT INTO auth_opportunity_grants VALUES(?,?)',[(user,opp) for user in ('DEMO-Pricing-Analyst','DEMO-BU-Head','DEMO-Finance','ADMIN','TECH') for opp in ('OP1','OP2')])
b=ThreadingHTTPServer(('127.0.0.1',0),server.PriceTrackHandler);threading.Thread(target=b.serve_forever,daemon=True).start();run_frontend.BACKEND=f'http://127.0.0.1:{b.server_port}'
f=ThreadingHTTPServer(('127.0.0.1',0),run_frontend.Handler);threading.Thread(target=f.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{f.server_port}'
class Client:
 def __init__(self):self.cookie='';self.csrf=''
 def req(self,path,method='GET',body=None,extra=None,direct=False,csrf=True):
  headers={'Content-Type':'application/json','X-PriceTrack-Request':'1'}
  if self.cookie:headers['Cookie']=self.cookie
  if csrf and self.csrf:headers['X-CSRF-Token']=self.csrf
  headers.update(extra or {})
  request=Request((run_frontend.BACKEND if direct else base)+path,method=method,data=None if body is None else json.dumps(body).encode(),headers=headers)
  try:
   with urlopen(request,timeout=20) as response:
    raw=response.read();data=json.loads(raw);cookie=response.headers.get('Set-Cookie');code=response.status
  except HTTPError as error:return error.code,json.loads(error.read())
  if cookie:self.cookie=cookie.split(';')[0];self.full_cookie=cookie
  if path=='/api/auth/login' and code==200:self.csrf=data['csrf_token'];self.user=data['user']
  return code,data
 def login(self,id):
  code,data=self.req('/api/auth/login','POST',dict(user_id=id,password=password));assert code==200,(id,code,data);return self
clients={}
try:
 guest=Client()
 for route in ['/api/dashboard','/api/opportunities','/api/users','/api/workbook-reference','/api/pricing-cases','/api/auth/me']:
  assert guest.req(route)[0]==401,(route,guest.req(route))
 assert guest.req('/api/health')[0]==200 and 'records' not in guest.req('/api/health')[1]
 assert guest.req('/api/pricing-cases','POST',{'opportunity_id':'OP1'})[0]==401
 assert guest.req('/api/auth/login','POST',dict(user_id='CP-1',password=password),extra={'Origin':'https://evil.example'})[0]==403
 assert guest.req('/api/auth/login','POST',dict(user_id='CP-1',password=password),extra={'X-PriceTrack-Request':''})[0]==403
 for name in ('CP-1','CP-2','DEMO-Pricing-Analyst','DEMO-BU-Head','DEMO-Finance','ADMIN','TECH','NONE'):clients[name]=Client().login(name)
 cp,other,analyst,bu,finance,admin,tech,none=[clients[name] for name in clients]
 assert 'HttpOnly' in cp.full_cookie and 'SameSite=Strict' in cp.full_cookie and 'Path=/api' in cp.full_cookie
 assert cp.req('/api/auth/me')[1]['user']['user_id']=='CP-1'
 assert cp.req('/api/opportunities')[1]['total']==1 and cp.req('/api/opportunities')[1]['opportunities'][0]['opportunity_id']=='OP1'
 assert cp.req('/api/opportunities/stages')[1]['stages']==[{'stage':'Needs'}]
 assert cp.req('/api/opportunities/OP2')[0]==403
 assert cp.req('/api/rates/client')[1]['rates'][0]['rate_id']=='RATE1' and len(cp.req('/api/rates/client')[1]['rates'])==1
 assert cp.req('/api/users')[0]==403 and admin.req('/api/users')[0]==200
 assert admin.req('/api/opportunities')[0]==403 and admin.req('/api/dashboard')[0]==403
 assert none.req('/api/dashboard')[1]['counts']['opportunities']==0
 assert none.req('/api/opportunities')[1]['total']==0
 assert cp.req('/api/pricing-cases','POST',{'opportunity_id':'OP1'},csrf=False)[0]==403
 assert cp.req('/api/pricing-cases','POST',{'opportunity_id':'OP1'},extra={'Origin':'https://evil.example'})[0]==403
 assert cp.req('/api/pricing-cases','POST',{'opportunity_id':'OP1'},extra={'Sec-Fetch-Site':'cross-site'})[0]==403
 assert cp.req('/api/pricing-cases','POST',{'opportunity_id':'OP2'})[0]==403
 code,created=cp.req('/api/pricing-cases','POST',{'opportunity_id':'OP1'});assert code==201,(code,created);case1=created['pricing_case']['case_id']
 code,created=other.req('/api/pricing-cases','POST',{'opportunity_id':'OP2'});assert code==201;case2=created['pricing_case']['case_id']
 for endpoint in ('resources','workbook-calculation','versions','approvals','negotiation','activity','readiness'):
  assert cp.req(f'/api/pricing-cases/{case2}/{endpoint}')[0]==404,endpoint
 assert cp.req(f'/api/pricing-cases/{case2.replace("-","%2D")}/resources',direct=True)[0]==404
 assert cp.req('/api/pricing-cases?case_id='+case2)[1]['pricing_cases']==[]
 assert len(cp.req('/api/pricing-cases')[1]['pricing_cases'])==1
 res=f'/api/pricing-cases/{case1}/resources';calc=f'/api/pricing-cases/{case1}/workbook-calculation';versions=f'/api/pricing-cases/{case1}/versions';reviews=f'/api/pricing-cases/{case1}/approvals';neg=f'/api/pricing-cases/{case1}/negotiation'
 plan=dict(expected_revision=0,months=['2027-01'],resources=[dict(id='R1',role='Engineer',hours=[None])])
 assert cp.req(res,'PUT',plan)[0]==403 and finance.req(res,'PUT',plan)[0]==403
 assert tech.req(res,'PUT',plan)[0]==200
 inputs=dict(vertical='RCM',bench=.05,onshore_cm=.5,offshore_cm=.5,onshore_hours=160,offshore_hours=160,resources=[dict(stream='onshore',rate_id='27',resource_id='R1',people=1,months=1,billability=.5)],ip=[],ip_revenue=0,simulation_cm=[.5,.99])
 payload=dict(expected_revision=0,resource_revision=1,inputs=inputs)
 assert finance.req(calc,'PUT',payload)[0]==403 and cp.req(calc,'PUT',payload)[0]==403
 assert analyst.req(calc,'PUT',payload)[0]==200
 assert analyst.req(versions,'PUT',{'expected_revision':1})[0]==200
 request=dict(expected_revision=0,version_number=1,action='submit',comment='Review requested')
 assert cp.req(reviews,'PUT',request)[0]==403
 assert analyst.req(reviews,'PUT',{**request,'actor_id':'DEMO-Finance'})[0]==403
 assert analyst.req(reviews,'PUT',request)[0]==200
 decision=dict(expected_revision=1,version_number=1,action='approve',comment='Reviewed')
 assert finance.req(reviews,'PUT',decision)[0]==403
 assert admin.req(reviews,'PUT',decision)[0]==403
 assert bu.req(reviews,'PUT',{**decision,'actor_id':'DEMO-Finance'})[0]==403
 assert bu.req(reviews,'PUT',decision)[0]==200
 decision['expected_revision']=2;assert finance.req(reviews,'PUT',decision)[0]==200
 review=finance.req(reviews)[1];assert review['versions'][0]['status']=='Approved in demo'
 assert review['actors']==[{'user_id':'DEMO-Finance','display_name':'Priya Demo','role':'Finance'}]
 discussion=dict(expected_revision=0,version_number=1,kind='Client Ask',note='Discussed revised scope',amount_usd='100.00')
 assert finance.req(neg,'PUT',discussion)[0]==403
 assert cp.req(neg,'PUT',{**discussion,'actor_id':'DEMO-Pricing-Analyst'})[0]==403
 assert cp.req(neg,'PUT',discussion)[0]==200
 assert cp.req(neg)[1]['events'][0]['actor_id']=='CP-1'
 visible=cp.req('/api/dashboard')[1];assert visible['counts']['cases']==1 and visible['counts']['saved_versions']==1 and visible['counts']['opportunities']==1
 assert other.req('/api/dashboard')[1]['counts']['cases']==1 and other.req('/api/dashboard')[1]['counts']['saved_versions']==0
 assert other.req('/api/dashboard')[1]['latest_version_revenue']['amount'] is None
 assert cp.req('/api/approval-inbox')[1]['items'][0]['case_id']==case1 and other.req('/api/approval-inbox')[1]['items']==[]
 events=analyst.req(f'/api/pricing-cases/{case1}/activity')[1]['events']
 assert any('signed-in local user' in event['actor'] and 'Maya Demo' in event['actor'] for event in events)
 assert cp.req(f'/api/pricing-cases/{case1}/readiness')[1]['ready_for_demo_review_request']==False
 # Role and scope changes are re-evaluated for existing sessions.
 with sqlite3.connect(database) as db:db.execute("DELETE FROM auth_opportunity_grants WHERE user_id='DEMO-Finance'")
 assert finance.req(reviews)[0]==404
 with sqlite3.connect(database) as db:db.execute("UPDATE users SET role='HR/MNH' WHERE user_id='DEMO-BU-Head'")
 assert bu.req(reviews,'PUT',dict(expected_revision=3,version_number=1,action='approve',comment='x'))[0]==403
 # Session persistence, expiry, disable, logout, and password reset.
 old=cp.cookie;assert cp.req('/api/auth/logout','POST',{})[0]==200
 cp.cookie=old;assert cp.req('/api/auth/me')[0]==401
 cp.login('CP-1');old=cp.cookie;auth.set_password(database,'CP-1',password);assert cp.req('/api/auth/me')[0]==401
 cp.login('CP-1')
 with sqlite3.connect(database) as db:db.execute("UPDATE users SET enabled=0 WHERE user_id='CP-1'")
 assert cp.req('/api/auth/me')[0]==401
 with sqlite3.connect(database) as db:db.execute("UPDATE auth_sessions SET expires_at=0 WHERE user_id='CP-2'")
 assert other.req('/api/auth/me')[0]==401
 bad=Client()
 for attempt in range(5):assert bad.req('/api/auth/login','POST',dict(user_id='UNKNOWN',password='wrong'))[0]==401
 assert bad.req('/api/auth/login','POST',dict(user_id='UNKNOWN',password='wrong'))[0]==429
 with sqlite3.connect(database) as db:
  stored=db.execute('SELECT salt,digest FROM auth_credentials').fetchall();assert len({row[0] for row in stored})==len(stored);assert all(password not in str(row) for row in stored)
  assert all(not token.startswith('pt_session=') for token, in db.execute('SELECT token_hash FROM auth_sessions'))
 assert guest.req('/api/dashboard',direct=True)[0]==401
 assert analyst.req('/api/dashboard',extra={'Host':'evil.example'},direct=True)[0]==403
 assert analyst.req('/api/dashboard',extra={'Host':'evil.example'})[0]==403
 assert analyst.req(res,'PUT',plan,extra={'X-CSRF-Token':'é'})[0]==403
 import subprocess
 def command(name):
  completed=subprocess.run([sys.executable,str(PROJECT_ROOT/'manage_users.py'),'--database',str(database),name,'--user-id','CP-2','--opportunity-id','OP2'],capture_output=True,text=True)
  assert completed.returncode==0,(completed.stdout,completed.stderr)
 other.login('CP-2');command('revoke-opportunity');assert other.req('/api/opportunities')[1]['total']==0
 with sqlite3.connect(database) as db:assert db.execute("SELECT COUNT(*) FROM user_opportunity_scope WHERE user_id='CP-2'").fetchone()[0]==1
 command('grant-opportunity');assert other.req('/api/opportunities')[1]['total']==1
 assert other.req('/api/auth/me')[0]==200
 with sqlite3.connect(database) as db:
  raw=other.cookie.split('=',1)[1];assert db.execute('SELECT 1 FROM auth_sessions WHERE token_hash=?',(hashlib.sha256(raw.encode()).hexdigest(),)).fetchone()
 print('PASS trusted CLI revocation overrides seeded scopes without modifying them; explicit grant restores access immediately.')
 print('PASS authenticated HTTP/proxy: password hashes, login cookie/CSRF, source/case/dashboard/rate/inbox scope, encoded URL checks, role writes, actor spoof rejection, sequential signed-in review, actual negotiation identity, scoped totals, live revocation, expiry/logout/reset/disable and throttling.')
finally:f.shutdown();b.shutdown();f.server_close();b.server_close()
