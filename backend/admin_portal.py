"""Password-only researcher portal. Bearer token is held in PAGE MEMORY ONLY.
Closing or refreshing admin webpage requires password again; no auth cookie or storage.
An issued token cannot be recalled on tab-close and expires in 30 minutes; never log tokens.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from export_reports import objects, read_json, build_export

HERE = Path(__file__).resolve().parent
SID_RE = re.compile(r'^[a-f0-9]{32}$')
LOGIN_MAX_ATTEMPTS = 7
LOGIN_WINDOW_SECONDS = 900
_failed = defaultdict(deque)
_password = PasswordHasher()


def _conf(name):
    value = os.getenv(name, '').strip()
    if not value:
        raise RuntimeError('Missing researcher security setting: ' + name)
    return value


def check_admin_config():
    p = _conf('ADMIN_PASSWORD_HASH')
    if not p.startswith('$argon2id$'):
        raise RuntimeError('ADMIN_PASSWORD_HASH must be an Argon2id hash, not a plaintext password')
    for key in ('ADMIN_SESSION_SECRET', 'STUDY_SECRET'):
        if len(_conf(key)) < 40:
            raise RuntimeError(key + ' must be at least 40 random characters')


def _signed(payload):
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()).rstrip(b'=')
    digest = hmac.new(_conf('ADMIN_SESSION_SECRET').encode(), encoded, hashlib.sha256).digest()
    return encoded.decode() + '.' + base64.urlsafe_b64encode(digest).rstrip(b'=').decode()



# Every private dashboard or download request needs a valid researcher token.
def _require(request):
    value = request.headers.get('authorization', '')
    if not value.startswith('Bearer ') or len(value) > 2000:
        raise HTTPException(401, 'Researcher sign in required')
    try:
        body, signature = value[7:].split('.', 1)
        mac = base64.urlsafe_b64decode(signature + '=' * (-len(signature)%4))
        expected = hmac.new(_conf('ADMIN_SESSION_SECRET').encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected):
            raise ValueError()
        obj = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body)%4)))
        if obj.get('role') != 'researcher' or obj.get('version') != 2 or int(obj.get('exp',0)) <= time.time():
            raise ValueError()
    except (ValueError, TypeError, KeyError, UnicodeError) as e:
        raise HTTPException(401, 'Session expired or invalid; sign in again') from e


def _ip(request):
    return request.client.host if request.client else 'unknown'


def _recent_failures(ip):
    now = time.monotonic()
    q = _failed[ip]
    while q and q[0] < now - LOGIN_WINDOW_SECONDS:
        q.popleft()
    return q


def _stream_file(file, filename):
    def reader():
        try:
            while True:
                block = file.read(256*1024)
                if not block: break
                yield block
        finally:
            file.close()
    return StreamingResponse(reader(), media_type='application/zip', headers={
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


def register(app, get_s3, get_bucket):
    @app.get('/admin', include_in_schema=False)
    @app.get('/admin/', include_in_schema=False)
    @app.get('/admin/login', include_in_schema=False)
    def dashboard_shell():
        # HTML shell is public; it contains NO private data and cannot call APIs until login.
        return FileResponse(HERE/'admin_dashboard.html', media_type='text/html', headers={'Cache-Control':'no-store'})

    # Check the password hash. The login response is held in page memory, not a cookie.
    @app.post('/admin/api/login', include_in_schema=False)
    async def login(request: Request):
        failures = _recent_failures(_ip(request))
        if len(failures) >= LOGIN_MAX_ATTEMPTS:
            raise HTTPException(429, 'Too many attempts. Try again later.')
        raw = await request.body()
        if len(raw) > 2048:
            raise HTTPException(413, 'Request too large')
        try:
            data = json.loads(raw)
            password = data.get('password', '')
        except (ValueError, TypeError, AttributeError):
            password = ''
        if not isinstance(password, str) or len(password) > 256:
            password = ''
        try:
            good = _password.verify(_conf('ADMIN_PASSWORD_HASH'), password)
        except (InvalidHashError, VerifyMismatchError):
            good = False
        if not good:
            failures.append(time.monotonic())
            raise HTTPException(401, 'Incorrect password')
        failures.clear()
        token = _signed({'role':'researcher', 'version':2,
                         'exp':int(time.time())+30*60, 'nonce':secrets.token_hex(16)})
        return JSONResponse({'token':token, 'expires_in_seconds':1800}, headers={'Cache-Control':'no-store'})

    # Count all saved sessions, but only load detailed rows for the latest 250.
    @app.get('/admin/api/sessions', include_in_schema=False)
    def sessions(request: Request):
        _require(request)
        s3, bucket = get_s3(), get_bucket()
        grouped = defaultdict(list)
        for item in objects(s3, bucket, 'sessions/'):
            parts = item['Key'].split('/')
            if len(parts) >= 3 and SID_RE.fullmatch(parts[1]):
                grouped[parts[1]].append(item)
        records = []
        counts = {'submitted':0, 'incomplete':0, 'uploading':0, 'receipt_error':0}
        for sid, items in grouped.items():
            keys = {v['Key'].rsplit('/',1)[-1] for v in items}
            item = {'session_id':sid, 'status':'uploading',
                    'batches':sum('/batches/' in x['Key'] for x in items),
                    'bytes':sum(int(x.get('Size',0)) for x in items),
                    'last_activity':None, 'visit':'pilot'}
            for obj in items:
                stamp = obj.get('LastModified')
                if isinstance(stamp, datetime):
                    iso = stamp.astimezone(timezone.utc).isoformat()
                    if not item['last_activity'] or iso > item['last_activity']:
                        item['last_activity'] = iso
            if 'completed.json.gz' in keys:
                try:
                    complete = read_json(s3, bucket, f'sessions/{sid}/completed.json.gz')
                    item['status'] = 'incomplete' if complete.get('partial') else 'submitted'
                except Exception:
                    item['status'] = 'receipt_error'
            counts[item['status']] = counts.get(item['status'],0)+1
            records.append(item)
        records.sort(key=lambda x:x['last_activity'] or '', reverse=True)
        # Only detailed metric reads are capped. Completion totals include all stored sessions.
        for item in records[:250]:
            sid = item['session_id']
            try:
                complete = read_json(s3, bucket, f'sessions/{sid}/completed.json.gz')
                seq = int(complete['last_sequence'])
                batch = read_json(s3, bucket, f'sessions/{sid}/batches/{seq:06d}.json.gz')
                summary = (batch.get('data') or {}).get('validation_summary') or {}
                item['metrics'] = {x:summary.get(x) for x in ('accPx','accDeg','precPx','precDeg','hz','validity')}
                item['validation_passed'] = (summary.get('screenQuality') or {}).get('pass')
            except Exception:
                pass
        return {'total_sessions':len(records), 'counts':counts,
                'sessions':records[:250], 'shown':min(250,len(records)),
                'refreshed_at':datetime.now(timezone.utc).isoformat()}

    # A researcher can download an individual session after signing in.
    @app.get('/admin/api/sessions/{session_id}/download', include_in_schema=False)
    def session_zip(session_id: str, request: Request):
        _require(request)
        if not SID_RE.fullmatch(session_id):
            raise HTTPException(404, 'Session not found')
        try:
            file = build_export(get_s3(), get_bucket(), session_id=session_id, max_size=120*1024*1024)
        except FileNotFoundError:
            raise HTTPException(404, 'Session not found')
        except OverflowError:
            raise HTTPException(413, 'Session too large for browser export')
        return _stream_file(file, f'webgazer_session_{session_id}.zip')

    # The full ZIP has the original records as well as tables and plots.
    @app.get('/admin/api/export-all', include_in_schema=False)
    def export_all(request: Request):
        _require(request)
        try:
            file = build_export(get_s3(), get_bucket(), max_size=350*1024*1024)
        except OverflowError:
            raise HTTPException(413, 'Dataset too large for one browser export. Use the protected CLI export script.')
        return _stream_file(file, 'webgazer_all_sessions_csv_plots_raw.zip')
