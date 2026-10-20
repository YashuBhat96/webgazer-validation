"""Run locally: python backend/make_admin_hash.py. Never store your password in git."""
from getpass import getpass
from argon2 import PasswordHasher
password=getpass('Choose a unique researcher password (16+ characters): ')
if len(password)<16:
    raise SystemExit('A researcher password must contain at least 16 characters.')
if password != getpass('Confirm password: '):
    raise SystemExit('The passwords did not match.')
print('Add this value to the ADMIN_PASSWORD_HASH Railway environment variable:')
print(PasswordHasher().hash(password))
