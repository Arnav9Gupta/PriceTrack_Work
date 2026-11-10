"""Trusted local operator: set credentials and explicit opportunity grants. No shared defaults."""
import argparse
import getpass
import sqlite3
from pathlib import Path
from pricing_auth import initialize, set_password, user_record

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--database',type=Path,default=Path(__file__).resolve().parent/'data'/'pricetrack.sqlite')
sub=parser.add_subparsers(dest='command',required=True)
sub.add_parser('list')
for name in ('set-password','grant-all','revoke-all','disable','enable'):
 item=sub.add_parser(name);item.add_argument('--user-id',required=True)
for name in ('grant-opportunity','revoke-opportunity'):
 item=sub.add_parser(name);item.add_argument('--user-id',required=True);item.add_argument('--opportunity-id',required=True)
args=parser.parse_args()
if not args.database.is_file():parser.error('Existing database not found. Use the project with your imported seed database.')
initialize(args.database)
try:
 with sqlite3.connect(args.database) as db:
  if args.command=='list':
   for row in db.execute('SELECT user_id,display_name,role,enabled FROM users ORDER BY role,display_name'):print(' | '.join(map(str,row)))
  else:
   if args.command in ('disable','enable'):
    if not db.execute('SELECT 1 FROM users WHERE user_id=?',(args.user_id,)).fetchone():raise ValueError('Seeded user not found.')
    db.execute('UPDATE users SET enabled=? WHERE user_id=?',(int(args.command=='enable'),args.user_id))
    db.execute('DELETE FROM auth_sessions WHERE user_id=?',(args.user_id,));print('Account status updated; sessions revoked.');db.commit();raise SystemExit(0)
   if not user_record(db,args.user_id):raise ValueError('Choose an enabled seeded user with a supported role.')
   if args.command=='set-password':
    password=getpass.getpass('New password (12–128 characters): ')
    if password!=getpass.getpass('Repeat password: '):raise ValueError('Passwords do not match.')
    set_password(args.database,args.user_id,password);print('Password set. Existing sessions for this user were revoked.')
   elif args.command=='grant-all':
    db.execute('DELETE FROM auth_opportunity_denials WHERE user_id=?',(args.user_id,))
    db.execute('INSERT OR IGNORE INTO auth_opportunity_grants SELECT ?,opportunity_id FROM salesforce_opportunities',(args.user_id,));print('Granted this user access to all currently imported opportunities. Role permissions still apply. Future opportunities require a new grant.')
   elif args.command=='revoke-all':
    db.execute('INSERT OR IGNORE INTO auth_opportunity_denials SELECT ?,opportunity_id FROM salesforce_opportunities',(args.user_id,))
    db.execute('DELETE FROM auth_opportunity_grants WHERE user_id=?',(args.user_id,));print('Access to currently imported opportunities revoked without editing seeded scopes. Disable the account to block all sign-in.')
   else:
    if not db.execute('SELECT 1 FROM salesforce_opportunities WHERE opportunity_id=?',(args.opportunity_id,)).fetchone():raise ValueError('Imported opportunity not found.')
    if args.command=='grant-opportunity':
     db.execute('DELETE FROM auth_opportunity_denials WHERE user_id=? AND opportunity_id=?',(args.user_id,args.opportunity_id))
     db.execute('INSERT OR IGNORE INTO auth_opportunity_grants VALUES(?,?)',(args.user_id,args.opportunity_id))
    else:
     db.execute('DELETE FROM auth_opportunity_grants WHERE user_id=? AND opportunity_id=?',(args.user_id,args.opportunity_id))
     db.execute('INSERT OR IGNORE INTO auth_opportunity_denials VALUES(?,?)',(args.user_id,args.opportunity_id))
    print('Opportunity access updated. Seeded scope rows remain unchanged.')
except ValueError as error:parser.exit(1,str(error)+'\n')
