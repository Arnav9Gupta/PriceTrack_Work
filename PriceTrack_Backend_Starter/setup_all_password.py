"""One-time local demo credential setup for every enabled imported user."""
import csv
import os
import secrets
import sqlite3
from pathlib import Path
from pricing_auth import initialize, set_password, user_record

ROOT = Path(__file__).resolve().parent

def main():
    database = ROOT / 'data' / 'pricetrack.sqlite'
    if not database.is_file():
        raise SystemExit('Imported database not found in data/pricetrack.sqlite.')
    initialize(database)
    with sqlite3.connect(database) as db:
        users = [row for row in db.execute('SELECT user_id,display_name,role FROM users ORDER BY user_id')
                 if user_record(db, row[0]) and not db.execute('SELECT 1 FROM auth_credentials WHERE user_id=?', (row[0],)).fetchone()]
    if not users:
        print('All eligible accounts already have passwords. No passwords changed.')
        return
    output = ROOT / ('LOCAL_LOGIN_PASSWORDS_' + secrets.token_hex(4) + '.csv')
    with output.open('x', newline='', encoding='utf-8') as stream:
        os.chmod(output, 0o600)
        writer = csv.writer(stream)
        writer.writerow(['User ID', 'Name', 'Role', 'Password'])
        for user_id, name, role in users:
            password = secrets.token_urlsafe(18)
            set_password(database, user_id, password)
            writer.writerow([user_id, name, role, password])
            stream.flush()
    print(f'Passwords created for {len(users)} accounts. Existing passwords retained.')
    print(f'Open this private local file to see the login details: {output}')
    print('Keep this file private and outside Git. Assigned opportunity access still applies.')

if __name__ == '__main__':
    main()
