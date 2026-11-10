"""Local password/session authentication and explicit opportunity-scoped permissions."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie, CookieError
from urllib.parse import urlsplit
from contextvars import ContextVar

SESSION_SECONDS=8*60*60
ITERATIONS=600000
CURRENT_ACTOR=ContextVar('pricing_authenticated_actor',default=None)
RIGHTS={
 'Client Partner':{'read','create','negotiate'},
 'Pricing Analyst':{'read','create','resources','calculate','version','submit','negotiate'},
 'Tech COE':{'read','resources'},
 'BU Head':{'read','review_bu'},
 'Finance':{'read','review_finance'},
 'HR/MNH':{'read'},
 'Admin':{'directory'},
}
class AuthError(Exception):
 def __init__(self,status,message):self.status=status;self.message=message;super().__init__(message)

def initialize(database):
 with sqlite3.connect(database) as db:
  for statement in [
   'CREATE TABLE IF NOT EXISTS auth_credentials(user_id TEXT PRIMARY KEY,salt TEXT NOT NULL,digest TEXT NOT NULL,iterations INTEGER NOT NULL)',
   'CREATE TABLE IF NOT EXISTS auth_sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,csrf TEXT NOT NULL,expires_at INTEGER NOT NULL)',
   'CREATE TABLE IF NOT EXISTS auth_throttle(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,until_at INTEGER NOT NULL)',
   'CREATE TABLE IF NOT EXISTS auth_opportunity_denials(user_id TEXT NOT NULL,opportunity_id TEXT NOT NULL,PRIMARY KEY(user_id,opportunity_id))',
   'CREATE TABLE IF NOT EXISTS auth_opportunity_grants(user_id TEXT NOT NULL,opportunity_id TEXT NOT NULL,PRIMARY KEY(user_id,opportunity_id))']:
   db.execute(statement)

def user_record(db,user_id):
 row=db.execute('SELECT user_id,display_name,role,enabled,cost_access FROM users WHERE user_id=?',(user_id,)).fetchone()
 if not row or row[3]!=1 or row[2] not in RIGHTS:return None
 return dict(user_id=row[0],display_name=row[1],role=row[2],cost_access=bool(row[4]),permissions=sorted(RIGHTS[row[2]]))

def opportunities(db,user):
 return {r[0] for r in db.execute('SELECT opportunity_id FROM user_opportunity_scope WHERE user_id=? UNION SELECT opportunity_id FROM auth_opportunity_grants WHERE user_id=? EXCEPT SELECT opportunity_id FROM auth_opportunity_denials WHERE user_id=?',(user['user_id'],user['user_id'],user['user_id']))} if 'read' in user['permissions'] else set()

def scope(database,user):
 with sqlite3.connect(database) as db:return opportunities(db,user)

def require(user,right):
 if right not in user['permissions']:raise AuthError(403,'Your role cannot perform this action.')

def require_opportunity(database,user,opportunity_id):
 if opportunity_id not in scope(database,user):raise AuthError(403,'This opportunity is outside your assigned access.')

def require_case(database,user,case_id):
 require(user,'read')
 with sqlite3.connect(database) as db:
  row=db.execute('SELECT opportunity_id FROM pricing_cases WHERE case_id=?',(case_id,)).fetchone()
  if not row or row[0] not in opportunities(db,user):raise AuthError(404,'Pricing case unavailable for your account.')

def set_password(database,user_id,password):
 if not isinstance(password,str) or not 12<=len(password)<=128:raise ValueError('Use a password with 12–128 characters.')
 salt=secrets.token_hex(16);digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),ITERATIONS).hex()
 with sqlite3.connect(database) as db:
  if not user_record(db,user_id):raise ValueError('Choose an enabled seeded user with a supported role.')
  db.execute('INSERT INTO auth_credentials VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET salt=excluded.salt,digest=excluded.digest,iterations=excluded.iterations',(user_id,salt,digest,ITERATIONS))
  db.execute('DELETE FROM auth_sessions WHERE user_id=?',(user_id,))
  db.execute('DELETE FROM auth_throttle')

def login(database,user_id,password,remote):
 if not isinstance(user_id,str) or not isinstance(password,str) or not 1<=len(user_id)<=100 or len(password)>128:raise AuthError(401,'Invalid user ID or password.')
 now=int(time.time());user_id=user_id.strip()
 keys=['ip:'+remote,'user:'+hashlib.sha256(user_id.encode()).hexdigest()]
 with sqlite3.connect(database,timeout=10) as db:
  db.execute('BEGIN IMMEDIATE')
  for key in keys:
   row=db.execute('SELECT failures,until_at FROM auth_throttle WHERE key=?',(key,)).fetchone()
   if row and row[1]>now and row[0]>=(30 if key.startswith('ip:') else 5):raise AuthError(429,'Too many sign-in attempts. Try again in 15 minutes.')
  credential=db.execute('SELECT salt,digest,iterations FROM auth_credentials WHERE user_id=?',(user_id,)).fetchone()
  salt,digest,iterations=credential or ('00'*16,'00'*32,ITERATIONS)
  candidate=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),iterations).hex()
  user=user_record(db,user_id)
  if not credential or not hmac.compare_digest(candidate,digest) or not user:
   for key in keys:
    db.execute('INSERT INTO auth_throttle VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET failures=CASE WHEN until_at>? THEN failures+1 ELSE 1 END,until_at=CASE WHEN until_at>? THEN until_at ELSE excluded.until_at END',(key,now+900,now,now))
   db.commit();raise AuthError(401,'Invalid user ID or password.')
  db.execute('DELETE FROM auth_throttle WHERE key=?',(keys[1],))
  db.execute('DELETE FROM auth_sessions WHERE expires_at<=?',(now,))
  token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
  db.execute('INSERT INTO auth_sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user_id,csrf,now+SESSION_SECONDS))
  return token,dict(user=user,csrf_token=csrf,expires_at=now+SESSION_SECONDS)

def session(database,headers):
 try:
  cookies=SimpleCookie();cookies.load(headers.get('Cookie',''));token=cookies['pt_session'].value
 except (KeyError,ValueError,CookieError):raise AuthError(401,'Sign in to continue.')
 if len(token)>200:raise AuthError(401,'Sign in to continue.')
 digest=hashlib.sha256(token.encode()).hexdigest()
 with sqlite3.connect(database) as db:
  row=db.execute('SELECT user_id,csrf,expires_at FROM auth_sessions WHERE token_hash=?',(digest,)).fetchone()
  user=user_record(db,row[0]) if row and row[2]>int(time.time()) else None
  if not user:raise AuthError(401,'Your session has expired or access was disabled. Sign in again.')
  return dict(user=user,csrf_token=row[1],expires_at=row[2],token_hash=digest)

def check_request(headers,write=False,csrf=None,login_request=False):
 try:host=urlsplit('http://'+headers.get('Host','')).hostname
 except ValueError:host=None
 if host not in ('localhost','127.0.0.1'):raise AuthError(403,'Use the local Price Track address.')
 if write:
  origin=headers.get('Origin')
  allowed=set(os.getenv('PRICE_TRACK_ALLOWED_ORIGINS','http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000,http://127.0.0.1:3000').split(','))
  if origin and origin not in allowed:raise AuthError(403,'Request origin is not allowed.')
  if headers.get('Sec-Fetch-Site')=='cross-site':raise AuthError(403,'Cross-site writes are not allowed.')
  if login_request:
   if headers.get('X-PriceTrack-Request')!='1':raise AuthError(403,'Use the Price Track sign-in form.')
  elif not csrf or not hmac.compare_digest(headers.get('X-CSRF-Token','').encode(),csrf.encode()):raise AuthError(403,'The request security token is missing or invalid. Reload and try again.')

def cookie(token='',clear=False):
 secure='; Secure' if os.getenv('PRICE_TRACK_SECURE_COOKIE')=='1' else ''
 return 'pt_session='+token+'; Path=/api; HttpOnly; SameSite=Strict; Max-Age='+('0' if clear else str(SESSION_SECONDS))+secure

def public_user(database,headers):
 result=session(database,headers);return {k:result[k] for k in ('user','csrf_token','expires_at')}
