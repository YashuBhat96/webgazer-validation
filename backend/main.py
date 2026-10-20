"""Open study submission through per-session bearer capabilities. No webcam imagery intentionally accepted."""
import base64
import gzip
import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from collections import defaultdict, deque
import secrets

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pathlib import Path
from urllib.parse import urlsplit
from admin_portal import register, check_admin_config
from pydantic import BaseModel, Field
from typing import Literal


def env(name: str) -> str:
    v = os.getenv(name, '').strip()
    if not v:
        raise RuntimeError(f'Missing required configuration: {name}')
    return v



# Give a session its own signed upload credential. This is not an admin login.
def sign(payload: dict, secret: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()).rstrip(b'=').decode()
    mac = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return body + '.' + base64.urlsafe_b64encode(mac).rstrip(b'=').decode()



# A submitted token must belong to a real, unexpired session before any data are accepted.
def verify(token: str, secret: str) -> dict:
    try:
        if len(token) > 1800:
            raise ValueError('oversize')
        body, sig = token.split('.')
        expected = sign(json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4))), secret).split('.')[1]
        if not hmac.compare_digest(sig, expected):
            raise ValueError('bad signature')
        data = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        if not isinstance(data, dict) or data.get('type') != 'session' or int(data.get('exp', 0)) <= time.time():
            raise ValueError('expired or malformed')
        if not re.fullmatch(r'[a-f0-9]{32}', data.get('sid', '')) or data.get('visit') != 'pilot':
            raise ValueError('invalid session')
        return data
    except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail='Invalid or expired submission token') from exc


# Lightweight protective throttling for prototype. This is per-process, not a distributed
# rate limiter: add an edge/WAF limit (or managed CAPTCHA) before inviting the public.
_ANON_IP_EVENTS = defaultdict(deque)
_ANON_MAX_PER_HOUR = int(os.getenv('PUBLIC_SESSION_MAX_PER_HOUR_PER_IP', '120'))


# Slow down repeated session requests from one client. This is only a basic limit.
def throttle_anonymous(request: Request):
    ip = request.client.host if request.client else 'unknown'
    q = _ANON_IP_EVENTS[ip]
    current = time.monotonic()
    while q and current - q[0] > 3600:
        q.popleft()
    if len(q) >= _ANON_MAX_PER_HOUR:
        raise HTTPException(status_code=429, detail='Too many new study sessions. Please try again later.')
    q.append(current)


@lru_cache(maxsize=1)
def s3():
    addr_style = os.getenv('S3_ADDRESS_STYLE', 'virtual')
    return boto3.client(
        's3', endpoint_url=env('S3_ENDPOINT'),
        aws_access_key_id=env('S3_ACCESS_KEY_ID'),
        aws_secret_access_key=env('S3_SECRET_ACCESS_KEY'),
        region_name=os.getenv('S3_REGION', 'auto'),
        config=Config(signature_version='s3v4', s3={'addressing_style': addr_style}, retries={'max_attempts': 3}),
    )


def bucket():
    return env('S3_BUCKET')


def object_exists(key):
    try:
        return s3().head_object(Bucket=bucket(), Key=key)
    except ClientError as exc:
        if exc.response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 404 or exc.response.get('Error', {}).get('Code') in ('404', 'NoSuchKey', 'NotFound'):
            return None
        raise



# Store one compressed record. A batch number should not silently overwrite different data.
def upload_json(key: str, value: dict, *, record_type: str = ''):
    contents = json.dumps(value, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    blob = gzip.compress(contents, mtime=0)
    sha = hashlib.sha256(contents).hexdigest()
    existing = object_exists(key)
    if existing:
        if existing.get('Metadata', {}).get('sha256') == sha:
            return {'status': 'already_stored', 'sha256': sha}
        raise HTTPException(status_code=409, detail='Batch number already used with different contents')
    # Explicit fail-on-overwrite supports concurrent duplicate requests on stores that honor conditional PutObject.
    # Object creation under unique keys is best-effort for S3-compatible implementations; verify with replay tests.
    s3().put_object(Bucket=bucket(), Key=key, Body=blob,
                    ContentType='application/json', ContentEncoding='gzip',
                    Metadata={'sha256': sha, 'kind': record_type})
    return {'status': 'stored', 'sha256': sha}


# One FastAPI service hosts the experiment, the private admin page, and the upload API.
app = FastAPI(title='WebGazer Study', docs_url=None, redoc_url=None, openapi_url=None)
FRONTEND = Path(__file__).resolve().parent.parent
STATIC_ASSETS = {
    'webgazer-2.0.1.js', 'quality.js', 'gaze_kinematics.js', 'deploy-config.js', 'upload.js',
    'measure-guide.webp', 'setup-guide.webp', 'card-guide.webp'
}

@app.on_event('startup')
def secure_startup():
    # A public deployment must fail closed when its secrets or object store are absent.
    check_admin_config()
    for key in ('S3_ENDPOINT', 'S3_ACCESS_KEY_ID', 'S3_SECRET_ACCESS_KEY', 'S3_BUCKET', 'PUBLIC_BASE_URL'):
        env(key)
    url = os.environ['PUBLIC_BASE_URL'].rstrip('/')
    parsed = urlsplit(url)
    if parsed.scheme not in ('https', 'http') or (parsed.scheme != 'https' and parsed.hostname not in ('localhost', '127.0.0.1')):
        raise RuntimeError('PUBLIC_BASE_URL must be HTTPS (except for localhost).')

# Check where API requests come from and add browser security headers.
# Origin checks are not a replacement for session or admin authentication.
@app.middleware('http')
async def security_headers(request: Request, call_next):
    # Same-origin participant POST and researcher login. Browser CORS is never a security boundary.
    origin = request.headers.get('origin')
    if origin and request.url.path.startswith(('/api/', '/admin/api/')):
        expected = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')
        if not expected:
            expected = f'{request.url.scheme}://{request.headers.get("host", "")}'
        if origin.rstrip('/') != expected:
            return Response('Cross-site requests are not accepted', status_code=403, media_type='text/plain')
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'camera=(self), microphone=()'
    if request.url.path.startswith(('/admin', '/api/')):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'"
    return response

@app.get('/', include_in_schema=False)
@app.get('/index.html', include_in_schema=False)
def participant_page():
    return FileResponse(FRONTEND/'index.html', media_type='text/html', headers={'Cache-Control':'no-store'})

@app.get('/models/{model_path:path}', include_in_schema=False)
def face_model(model_path: str):
    base=(FRONTEND/'models').resolve()
    target=(base/model_path).resolve()
    if not target.is_relative_to(base) or not target.is_file() or target.name.startswith('.'):
        raise HTTPException(404, 'Model file not found')
    return FileResponse(target)

def frontend_asset(filename: str):
    return FileResponse(FRONTEND/filename, headers={'Cache-Control':'no-store'})

# Exact routes only: never accidentally expose backend source, credentials, exports, or .env.
for asset_name in sorted(STATIC_ASSETS):
    app.add_api_route('/' + asset_name, lambda filename=asset_name: frontend_asset(filename),
                      methods=['GET'], include_in_schema=False)



class StartRequest(BaseModel):
    pass


class CompleteRequest(BaseModel):
    last_sequence: int = Field(ge=0, le=599)


class BatchRequest(BaseModel):
    kind: Literal['consent', 'setup_failure', 'setup_complete', 'calibration_check', 'task_aborted', 'validation_complete', 'finish', 'incomplete_finish', 'kinematic_samples', 'movement_candidates', 'analysis_manifest', 'periodic_gaze', 'search_aborted', 'search_trial', 'search_complete']
    build: str = Field(max_length=120)
    created_at: str = Field(max_length=50)
    data: dict


def identify(authorization: str | None) -> tuple[str, dict]:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Submission token required')
    data = verify(authorization[7:], env('STUDY_SECRET'))
    return data['sid'], data


@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'webgazer-ingest'}


# The public study does not require invitations. It still issues a private upload token.
@app.post('/api/public-session')
def public_session(request: Request):
    # Public registration is not a data upload. Every user gets an unguessable, scoped
    # capability; no invitation, public listing or reading endpoint is available.
    if os.getenv('PUBLIC_STUDY_ENABLED', 'true').lower() not in ('true', '1', 'yes'):
        raise HTTPException(503, 'This study is not currently accepting new sessions')
    throttle_anonymous(request)
    sid = secrets.token_hex(16)
    expiry = int(time.time()) + 72 * 3600
    token = sign({'type': 'session', 'sid': sid, 'visit': 'pilot', 'exp': expiry}, env('STUDY_SECRET'))
    return {'session_id': sid, 'token': token, 'expires_at': expiry, 'visit': 'pilot'}


@app.post('/api/sessions')
def start(req: StartRequest, authorization: str | None = Header(default=None)):
    session_id, data = identify(authorization)
    key = f'sessions/{session_id}/start.json.gz'
    if not object_exists(key):
        upload_json(key, {'session_id': session_id, 'visit': data['visit'],
                          'started_at': datetime.now(timezone.utc).isoformat()})
    return {'session_id': session_id, 'status': 'ready'}


# Participants can write only to their own session, subject to size and count limits.
@app.post('/api/sessions/{session_id}/batches/{seq}')
async def batch(session_id: str, seq: int, request: Request, authorization: str | None = Header(default=None)):
    sid, data = identify(authorization)
    if session_id != sid:
        raise HTTPException(403, 'Session mismatch')
    if seq < 0 or seq > 599:
        raise HTTPException(400, 'Invalid sequence number')
    claimed = request.headers.get('content-length')
    if claimed and (not claimed.isdigit() or int(claimed) > 3_000_000):
        raise HTTPException(413, 'Batch too large')
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 3_000_000:
            raise HTTPException(413, 'Batch too large')
        chunks.append(chunk)
    body = b''.join(chunks)
    try:
        payload = BatchRequest.model_validate_json(body)
    except Exception as exc:
        raise HTTPException(422, 'Invalid batch JSON') from exc
    # Consent is recorded as the first upload for each session, not inferred from a click later.
    if seq == 0 and payload.kind != 'consent':
        raise HTTPException(422, 'First batch must contain consent acknowledgment')
    if payload.kind == 'consent':
        consent = payload.data
        if seq != 0 or consent.get('agreed') is not True or not isinstance(consent.get('typed_name'), str) or not consent['typed_name'].strip() or not consent.get('version') or not consent.get('acknowledged_at'):
            raise HTTPException(422, 'Consent record missing or incomplete')
    key = f'sessions/{sid}/batches/{seq:06d}.json.gz'
    if object_exists(f'sessions/{sid}/completed.json.gz') and not object_exists(key):
        raise HTTPException(409, 'Session already submitted. New batches cannot be appended.')
    # Bound abuse by number of objects AND cumulative compressed bucket usage.
    # Preserve existing chunks on failed retries; do not silently overwrite.
    existing_files = s3().list_objects_v2(Bucket=bucket(), Prefix=f'sessions/{sid}/', MaxKeys=1000).get('Contents', [])
    if len(existing_files) >= 605 or sum(int(obj.get('Size', 0)) for obj in existing_files) >= 100 * 1024 * 1024:
        raise HTTPException(413, 'Session upload storage limit reached')
    response = upload_json(key, {'visit': data['visit'], 'sequence': seq,
                                 **payload.model_dump()}, record_type=payload.kind)
    return {'sequence': seq, **response}


# Mark the submission complete only when every numbered batch exists.
@app.post('/api/sessions/{session_id}/complete')
def complete(session_id: str, req: CompleteRequest, authorization: str | None = Header(default=None)):
    sid, data = identify(authorization)
    if sid != session_id:
        raise HTTPException(403, 'Session mismatch')
    completion_key = f'sessions/{sid}/completed.json.gz'
    old_completion=object_exists(completion_key)
    if old_completion:
        return {'status': 'acknowledged', 'session_id': sid, 'already_completed': True,
                'partial':old_completion.get('Metadata',{}).get('kind')=='partial'}
    # One paginated S3 listing instead of hundreds of slow HEAD requests.
    prefix=f'sessions/{sid}/batches/'
    present=set(); continuation=None
    while True:
        kwargs={'Bucket':bucket(), 'Prefix':prefix, 'MaxKeys':1000}
        if continuation:kwargs['ContinuationToken']=continuation
        listing=s3().list_objects_v2(**kwargs)
        for obj in listing.get('Contents',[]):
            name=obj['Key'].removeprefix(prefix)
            if re.fullmatch(r'[0-9]{6}\.json\.gz',name):present.add(int(name[:6]))
        continuation=listing.get('NextContinuationToken')
        if not continuation:break
    missing=next((n for n in range(req.last_sequence+1) if n not in present),None)
    if missing is not None:
        raise HTTPException(409, f'Upload incomplete: missing batch {missing}')
    consent_meta=object_exists(f'{prefix}000000.json.gz')
    if not consent_meta or consent_meta.get('Metadata', {}).get('kind') != 'consent':
        raise HTTPException(409, 'Consent acknowledgment has not arrived')
    last_meta=object_exists(f'{prefix}{req.last_sequence:06d}.json.gz')
    if not last_meta or last_meta.get('Metadata', {}).get('kind') not in ('finish','incomplete_finish'):
        raise HTTPException(409, 'Cannot finalize: the final study checkpoint has not arrived')
    is_partial = last_meta.get('Metadata', {}).get('kind')=='incomplete_finish'
    upload_json(completion_key, {'session_id':sid,
         'visit':data['visit'], 'last_sequence':req.last_sequence, 'complete_client_ack':True, 'partial':is_partial},
                record_type='partial' if is_partial else 'complete')
    return {'status': 'acknowledged', 'session_id': sid, 'partial':is_partial}


# Admin routes use a separate researcher password token, never the participant token.
register(app, lambda: s3(), lambda: bucket())
