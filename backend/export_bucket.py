"""Export raw participant batches for local researcher analysis.

Run on an authorized researcher's computer with Railway bucket credentials in environment.
Outputs contain study data: keep them in approved encrypted research storage.
"""
import argparse
import csv
import gzip
import json
from pathlib import Path
from main import bucket, s3

p=argparse.ArgumentParser()
p.add_argument('--out',default='research_export',help='Approved protected output folder')
a=p.parse_args()
out=Path(a.out);out.mkdir(parents=True,exist_ok=True)


# Group the stored batches by internal session ID. No public participant identifier is used.
by_session={}
continuation=None
while True:
    args={'Bucket':bucket(),'Prefix':'sessions/'}
    if continuation:args['ContinuationToken']=continuation
    r=s3().list_objects_v2(**args)
    for item in r.get('Contents',[]):
        key=item['Key']
        if '/batches/' not in key or not key.endswith('.json.gz'):continue
        parts=key.split('/')
        if len(parts)!=4:continue
        sid=parts[1]
        binary=s3().get_object(Bucket=bucket(),Key=key)['Body'].read()
        payload=json.loads(gzip.decompress(binary))
        by_session.setdefault(sid,[]).append(payload)
    continuation=r.get('NextContinuationToken')
    if not continuation:break



# Each list of recorded values becomes its own table for analysis.
def csv_write(path,records):
    if not records:return
    headers=list(dict.fromkeys(k for r in records for k in r))
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=headers);w.writeheader()
        for row in records:
            w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})

for sid,batches in by_session.items():
    folder=out/sid;folder.mkdir(exist_ok=True)
    batches.sort(key=lambda b:b.get('sequence',0))
    expected=list(range(max((b.get('sequence',0) for b in batches),default=-1)+1))
    actual=[b.get('sequence') for b in batches]
    raws=[];attempts=[];checks=[];trials=[];summaries=[];kinematics=[];movements=[];manifests=[];participant_details=[]
    for batch in batches:
        data=batch.get('data') or {};seq=batch.get('sequence');pi=data.get('page_instance')
        for field,collection in [('gaze_events',raws),('attempts',attempts),('checks',checks),('search_trials',trials)]:
            for row in data.get(field) or []:
                collection.append({'batch_sequence':seq,'page_instance':pi,**row})
        for field,collection in [('samples',kinematics),('events',movements)]:
            for row in data.get(field) or []:
                collection.append({'batch_sequence':seq,'page_instance':pi,**row})
        if data.get('participant_details') is not None:
            participant_details.append({'batch_sequence':seq,'details':data['participant_details']})
        if data.get('analysis_parameters') is not None:
            manifests.append({'batch_sequence':seq,'parameters':data['analysis_parameters'],'summary':data.get('summary')})
        for field in ('validation_summary','search_summary'):
            if data.get(field) is not None:
                summaries.append({'batch_sequence':seq,'kind':field,'value':data[field]})
    csv_write(folder/'gaze_events.csv',raws)
    csv_write(folder/'attempts.csv',attempts)
    csv_write(folder/'gaze_kinematic_samples.csv',kinematics)
    csv_write(folder/'movement_candidates.csv',movements)
    (folder/'analysis_manifest.json').write_text(json.dumps(manifests,indent=2))
    # Contains an optional NAME and sensitive demographics: restrict access.
    (folder/'participant_details_RESTRICTED.json').write_text(json.dumps(participant_details,indent=2))
    with (folder/'checks.json').open('w') as f:json.dump(checks,f,indent=2)
    with (folder/'search_trials.json').open('w') as f:json.dump(trials,f,indent=2)
    with (folder/'summaries.json').open('w') as f:json.dump(summaries,f,indent=2)
    (folder/'audit.json').write_text(json.dumps({'session_id':sid,'batches':len(actual),
        'missing_sequences':sorted(set(expected)-set(actual)),'gaze_events':len(raws),
        'search_trials_saved':len(trials),'kinematic_samples':len(kinematics),
        'movement_candidates':len(movements),'attempts':len(attempts)},indent=2))
print(f'Exported {len(by_session)} sessions to {out}. Treat the folder as protected research data.')
