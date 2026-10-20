#!/usr/bin/env python3
"""Create a quality comparison table from gaze_session_*.json downloads.

Usage: python compare_sessions.py /path/to/downloads --out quality_comparison.csv
The program does not claim statistical significance or eye-tracker equivalence.
"""
import argparse,csv,json,pathlib,statistics

FIELDS=['participant','visit_type','operator_role','build','calibration_passed','validation_passed',
        'usable_points','acc_px','acc_deg','precision_px','precision_deg','coverage_pct',
        'callback_valid_pct','observed_rate_hz','inter_sample_ms','reasons','filename']
# Read one session summary and pull out the quality measures we use for comparisons.
def parse(path):
    d=json.loads(path.read_text(encoding='utf8'))
    m=d.get('measured_quality',{});q=d.get('session_outcome') or {}
    return {'participant':d.get('participant',''), 'visit_type':d.get('visit_type',''),
        'operator_role':d.get('operator_role',''),'build':d.get('study_build',''),
        'calibration_passed':d.get('calibration_check_passed'),
        'validation_passed':q.get('pass'), 'usable_points':d.get('validation_usable_points'),
        'acc_px':m.get('accuracy_mean_px'),'acc_deg':m.get('accuracy_deg'),
        'precision_px':m.get('precision_rms_px'),'precision_deg':m.get('precision_deg'),
        'coverage_pct':m.get('mean_time_coverage_pct'),
        'callback_valid_pct':m.get('callback_valid_pct'),
        'observed_rate_hz':m.get('sampling_hz'),
        'inter_sample_ms':m.get('inter_sample_mean_ms'),
        'reasons':';'.join(q.get('reasons') or []),'filename':path.name}
# Make one table across sessions. Group statistics here are only descriptive.
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=pathlib.Path)
    parser.add_argument('--out',default='quality_comparison.csv')
    args=parser.parse_args()
    files=sorted(args.directory.glob('gaze_session_*.json'))
    if not files:parser.error('No gaze_session_*.json files in directory')
    rows=[parse(f) for f in files]
    with open(args.out,'w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    keys={};duplicates=[]
    for r in rows:
        key=(r['participant'],r['visit_type'],r['operator_role'])
        if key in keys:duplicates.append(key)
        keys[key]=r
    print(f'Exported {len(rows)} session summaries to {args.out}')
    if duplicates:print('WARNING: duplicate participant-visit-group labels:',duplicates)
    for group in ['participant','expert']:
        in_group=[r for r in rows if r['operator_role']==group]
        if not in_group:continue
        passes=sum(r['validation_passed'] is True for r in in_group)
        print(f'{group}: {passes}/{len(in_group)} passed the twelve point validation screen')
        for visit in ['training','testing']:
            vals=[r['acc_px'] for r in in_group if r['visit_type']==visit and r['validation_passed'] is True and isinstance(r['acc_px'],(int,float))]
            if vals:print(f'  {visit}: {len(vals)} eligible summary values, mean error {statistics.mean(vals):.1f} CSS px')
    print('Group comparisons are descriptive; include failures and predeclare missing-data handling.')
if __name__=='__main__':main()
