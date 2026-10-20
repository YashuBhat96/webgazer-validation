import os,sys,time,io,json,gzip,zipfile,secrets,secrets
from pathlib import Path
from datetime import datetime, timezone
from argon2 import PasswordHasher
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEST_ADMIN_PASSWORD = secrets.token_urlsafe(32)
TEST_ADMIN_PASSWORD = secrets.token_urlsafe(32)
os.environ.update({
'STUDY_SECRET':secrets.token_urlsafe(48),
'S3_BUCKET':'test-bucket', 'PUBLIC_BASE_URL':'https://study.example.org',
'ADMIN_PASSWORD_HASH':PasswordHasher().hash(TEST_ADMIN_PASSWORD),
'ADMIN_SESSION_SECRET':secrets.token_urlsafe(48),
'S3_ENDPOINT':'https://example.invalid','S3_ACCESS_KEY_ID':secrets.token_urlsafe(24),'S3_SECRET_ACCESS_KEY':secrets.token_urlsafe(48),
})
import main

class MemoryBucket:
 def __init__(self):self.data={}
 def head_object(self,Bucket,Key):
  if Key not in self.data:raise ClientError({'Error':{'Code':'404'},'ResponseMetadata':{'HTTPStatusCode':404}},'HeadObject')
  return {'Metadata':self.data[Key]['Metadata'],'Size':len(self.data[Key]['Body'])}
 def list_objects_v2(self,Bucket,Prefix,MaxKeys=1000,ContinuationToken=None):
  keys=sorted(k for k in self.data if k.startswith(Prefix));offset=int(ContinuationToken or 0);portion=keys[offset:offset+MaxKeys]
  result={'Contents':[{'Key':k,'Size':len(self.data[k]['Body']),'LastModified':datetime.now(timezone.utc)} for k in portion]}
  if offset+MaxKeys<len(keys):result['NextContinuationToken']=str(offset+MaxKeys)
  return result
 def put_object(self,Bucket,Key,Body,ContentType,ContentEncoding,Metadata):self.data[Key]={'Body':Body,'Metadata':Metadata}
 def get_object(self,Bucket,Key):
  if Key not in self.data:raise KeyError(Key)
  return {'Body':io.BytesIO(self.data[Key]['Body'])}
store=MemoryBucket()
main.s3=lambda:store
client=TestClient(main.app,base_url='https://study.example.org')

def open_session():
 r=client.post('/api/public-session',headers={'Origin':'https://study.example.org'})
 assert r.status_code==200,r.text
 data=r.json();return data['session_id'],{'Authorization':'Bearer '+data['token'],'Origin':'https://study.example.org'}

def test_public_page_and_open_session():
 assert client.get('/').status_code==200
 assert client.get('/health').json()['status']=='ok'
 assert client.post('/api/sessions',json={}).status_code==401
 sid,headers=open_session()
 assert len(sid)==32
 assert client.post('/api/sessions',headers=headers,json={}).json()['session_id']==sid
 assert client.get('/admin/api/sessions',headers=headers).status_code==401
 assert client.get('/admin/api/export-all',headers=headers).status_code==401
 assert client.get('/admin/api/sessions/'+sid+'/download',headers=headers).status_code==401

def test_upload_dedup_complete_and_separation():
 sid,head=open_session()
 assert client.post('/api/sessions',headers=head,json={}).status_code==200
 base={'build':'v2.6','created_at':'2026-10-20T15:00:00Z','kind':'validation_complete',
       'data':{'gaze_events':[{'t':42,'rawX':101,'rawY':190,'phase':'validation'}],
       'validation_summary':{'accPx':80,'accDeg':1.2,'screenQuality':{'pass':True},
       'results':[{'accPx':120},{'accPx':75}]},'participant_details':{'optional_name':'Test'} }}
 url=f'/api/sessions/{sid}/batches/0'
 consent={**base,'kind':'consent','data':{'agreed':True,'typed_name':'Test','version':'consent-v1','acknowledged_at':'2026-10-20T15:00:00Z'}}
 assert client.post(url,headers=head,json=base).status_code==422  # no consent, no upload
 assert client.post(url,headers=head,json=consent).json()['status']=='stored'
 assert client.post(url,headers=head,json=consent).json()['status']=='already_stored'
 assert client.post(url,headers=head,json={**consent,'data':{'x':4}}).status_code==422
 assert client.post(f'/api/sessions/{sid}/complete',headers=head,json={'last_sequence':0}).status_code==409
 assert client.post(f'/api/sessions/{sid}/batches/1',headers=head,json=base).status_code==200
 finish={**base,'kind':'finish','data':{**base['data'], 'search_trials':[{'trial':1,'hit':True}]}}
 assert client.post(f'/api/sessions/{sid}/batches/2',headers=head,json=finish).status_code==200
 assert client.post(f'/api/sessions/{sid}/complete',headers=head,json={'last_sequence':2}).json()['status']=='acknowledged'
 assert client.post(f'/api/sessions/{sid}/batches/3',headers=head,json=base).status_code==409
 other_sid,other_head=open_session()
 assert client.post(f'/api/sessions/{sid}/complete',headers=other_head,json={'last_sequence':2}).status_code==403
 assert client.post(f'/api/sessions/{other_sid}/batches/600',headers=other_head,json=base).status_code==400
 return sid

def test_admin_login_password_only_memory_bearer_and_counts():
 sid=test_upload_dedup_complete_and_separation()
 assert client.get('/admin').status_code==200 # only login shell, no stored study data
 assert client.get('/admin/api/sessions').status_code==401
 assert client.post('/admin/api/login',json={'password':'wrong'}).status_code==401
 r=client.post('/admin/api/login',json={'password':TEST_ADMIN_PASSWORD})
 assert r.status_code==200,r.text
 assert not r.headers.get('set-cookie')
 token=r.json()['token'];headers={'Authorization':'Bearer '+token}
 assert client.get('/admin/api/sessions').status_code==401 # no cookies or persistent auth
 data=client.get('/admin/api/sessions',headers=headers).json()
 assert data['counts']['submitted']>=1
 assert data['counts']['submitted']==sum(r['status']=='submitted' for r in data['sessions'])
 assert data['total_sessions']>=1
 assert client.get('/admin/api/export-all',headers={'Authorization':'Bearer not-valid'}).status_code==401
 r=client.get('/admin/api/export-all',headers=headers)
 assert r.status_code==200,r.text
 with zipfile.ZipFile(io.BytesIO(r.content)) as zipped:
  names=zipped.namelist()
  assert 'study_summary.csv' in names
  assert any(n.endswith('/csv/gaze_events.csv') for n in names)
  assert any(n.endswith('/plots/gaze_scatter_pixels.png') for n in names)
  assert any(n.endswith('/plots/accuracy_by_point.png') for n in names)
  assert any(n.endswith('.json.gz') for n in names)
  assert 'Test' in zipped.read('sessions/'+sid+'/csv/other_fields.csv').decode('utf-8-sig')
 r=client.get('/admin/api/sessions/'+sid+'/download',headers=headers)
 assert r.status_code==200 and r.content[:2]==b'PK'
 assert client.get('/admin/api/sessions/'+sid+'/download').status_code==401
 assert client.get('/admin/api/invitations',headers=headers).status_code==404
 assert client.post('/admin/api/invitations',headers=headers,json={}).status_code==404

def test_cross_origin_path_restriction_and_expiry():
 sid,h=open_session()
 assert client.post('/api/sessions',headers={**h,'Origin':'https://evil.example'},json={}).status_code==403
 assert client.post('/api/public-session',headers={'Origin':'https://evil.example'}).status_code==403
 assert client.post('/admin/api/login',headers={'Origin':'https://evil.example'},json={}).status_code==403
 assert client.get('/backend/main.py').status_code==404
 assert client.get('/.env').status_code==404
 expired=main.sign({'type':'session','visit':'pilot','sid':sid,'exp':1},os.environ['STUDY_SECRET'])
 assert client.post('/api/sessions',headers={'Authorization':'Bearer '+expired},json={}).status_code==401
 assert client.get('/admin/api/export-all').status_code==401

def test_study_kill_switch_and_startup(monkeypatch):
 monkeypatch.setenv('PUBLIC_STUDY_ENABLED','false')
 assert client.post('/api/public-session').status_code==503
 monkeypatch.setenv('PUBLIC_STUDY_ENABLED','true')
 with TestClient(main.app,base_url='https://study.example.org') as t:
  assert t.get('/health').status_code==200
