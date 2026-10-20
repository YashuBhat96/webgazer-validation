"""Researcher-only CSV, raw JSON and PNG study exports.

Generated on demand; protected admin routes must authorize callers BEFORE this module is called.
Do not use generated files outside approved research data handling procedures.
"""
from __future__ import annotations
import csv
import gzip
import io
import json
import math
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timezone



# Read every page of object names, not just the first 1,000 stored files.
def objects(client, bucket, prefix):
    cursor = None
    while True:
        args = {'Bucket': bucket, 'Prefix': prefix, 'MaxKeys': 1000}
        if cursor:
            args['ContinuationToken'] = cursor
        data = client.list_objects_v2(**args)
        yield from data.get('Contents', [])
        cursor = data.get('NextContinuationToken')
        if not cursor:
            return


def read_json(client, bucket, key):
    payload = client.get_object(Bucket=bucket, Key=key)['Body'].read()
    return json.loads(gzip.decompress(payload))


def status_for(items):
    keys = {x['Key'].split('/')[-1] for x in items}
    if 'completed.json.gz' in keys:
        return 'submitted'
    return 'not_submitted'



# Free text beginning with spreadsheet formulas is escaped in the CSV exports.
def _safe_csv(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    if v is None:
        return ''
    if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + v  # avoid spreadsheet formula injection from free-text demographics
    return v


def _csv_content(rows):
    if not rows:
        return b''
    fields = list(dict.fromkeys(k for r in rows for k in r))
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    for record in rows:
        writer.writerow({k: _safe_csv(record.get(k)) for k in fields})
    return out.getvalue().encode('utf-8-sig')


def _as_row(value):
    return value if isinstance(value, dict) else {'value': value}


def _png_plot(xs, ys, xlabel, ylabel, title, kind='scatter'):
    if not xs:
        return None
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4.6))
    if kind == 'line':
        ax.plot(xs, ys, linewidth=0.9, alpha=0.8)
    elif kind == 'bar':
        ax.bar(xs, ys)
    else:
        ax.scatter(xs, ys, s=5, alpha=0.35)
    ax.set(xlabel=xlabel, ylabel=ylabel, title=title)
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    f = io.BytesIO()
    fig.savefig(f, format='png', dpi=140)
    plt.close(fig)
    return f.getvalue()


def _finite(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None



# Keep the original compressed JSON and make easier-to-analyze tables beside it.
def _session_export(z, s3, bucket, sid, items, prefix=''):
    base = prefix + 'sessions/' + sid + '/'
    collections = defaultdict(list)
    summaries = []
    batches = []
    manifest = {'session_id': sid, 'status': status_for(items), 'generated_at': datetime.now(timezone.utc).isoformat()}
    for item in sorted(items, key=lambda x: x['Key']):
        key = item['Key']
        if not key.endswith('.json.gz'):
            continue
        data_bytes = s3.get_object(Bucket=bucket, Key=key)['Body'].read()
        z.writestr(base + 'raw/' + key.split('sessions/' + sid + '/', 1)[-1], data_bytes)
        data = json.loads(gzip.decompress(data_bytes))
        filename = key.rsplit('/', 1)[-1]
        if filename == 'start.json.gz':
            manifest['start'] = data
        elif filename == 'completed.json.gz':
            manifest['completion'] = data
            manifest['status'] = 'incomplete' if data.get('partial') else 'submitted'
        elif '/batches/' in key:
            seq, kind = data.get('sequence'), data.get('kind')
            batches.append({'sequence': seq, 'kind': kind, 'timestamp': data.get('created_at'), 'build': data.get('build')})
            content = data.get('data') or {}
            for field, value in content.items():
                if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
                    # Include any future experiment table without changing the exporter.
                    for row in value:
                        collections[field].append({'session_id': sid, 'batch_sequence': seq, **row})
                else:
                    # Every other source field is retained in a typed JSON column.
                    summaries.append({'session_id': sid, 'batch_sequence': seq, 'field': field,
                                      'value': json.dumps(value, ensure_ascii=False)})
                if field == 'validation_summary' and isinstance(value, dict):
                    for point in value.get('results') or []:
                        if isinstance(point, dict):
                            collections['validation_points'].append({'session_id':sid,
                                'batch_sequence':seq, **point})
    for field, rows in collections.items():
        z.writestr(base + 'csv/' + field + '.csv', _csv_content(rows))
    z.writestr(base + 'csv/batches.csv', _csv_content(batches))
    z.writestr(base + 'csv/other_fields.csv', _csv_content(summaries))
    z.writestr(base + 'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    sample_rows = collections.get('gaze_events') or []
    gx, gy, gt = [], [], []
    for row in sample_rows[::max(1, len(sample_rows)//15000)]:
        x, y, t = _finite(row.get('rawX', row.get('x'))), _finite(row.get('rawY', row.get('y'))), _finite(row.get('t'))
        if x is not None and y is not None:
            gx.append(x); gy.append(y)
            if t is not None:
                gt.append(t)
    if gx:
        # Screen origin is upper left; visual plot follows the same convention.
        graphic = _png_plot(gx, gy, 'Gaze X (CSS pixels)', 'Gaze Y (CSS pixels)', 'Raw predicted gaze coordinates')
        if graphic:
            z.writestr(base + 'plots/gaze_scatter_pixels.png', graphic)
    if len(gt) == len(gx) and gt:
        graphic = _png_plot([t/1000 for t in gt], gx, 'Elapsed time (seconds)', 'Gaze X (CSS pixels)', 'Predicted horizontal gaze versus time', kind='line')
        if graphic:
            z.writestr(base + 'plots/gaze_x_over_time.png', graphic)
    points = []
    for row in summaries:
        if row['field'] == 'validation_summary':
            try:
                value = json.loads(row['value'])
                if isinstance(value.get('results'), list):
                    points = value['results']
            except (ValueError, TypeError):
                pass
    pts_x, pts_y = [], []
    for i, point in enumerate(points):
        if not isinstance(point, dict):
            continue
        err = _finite(point.get('accPx'))
        if err is not None:
            pts_x.append(i+1); pts_y.append(err)
    if pts_x:
        graphic = _png_plot(pts_x, pts_y, 'Validation point', 'Accuracy error (pixels)', 'Error by validation point', kind='line')
        if graphic:
            z.writestr(base + 'plots/accuracy_by_point.png', graphic)
    accuracy = precision = accuracy_deg = precision_deg = None
    for record in reversed(summaries):
        if record['field'] == 'validation_summary':
            try:
                summary = json.loads(record['value'])
                accuracy, precision = summary.get('accPx'), summary.get('precPx')
                accuracy_deg, precision_deg = summary.get('accDeg'), summary.get('precDeg')
                break
            except (TypeError, ValueError): pass
    return {'session_id': sid, 'status': manifest['status'],
            'accuracy_px':accuracy, 'accuracy_deg':accuracy_deg,
            'precision_px':precision, 'precision_deg':precision_deg,
            'gaze_samples': len(sample_rows),
            'search_trials': len(collections.get('search_trials') or []), 'batches': len(batches),
            'candidate_movements': len(collections.get('events') or [])}



# One session or the whole study can be exported as a ZIP of raw records, CSVs, and plots.
def build_export(s3, bucket, session_id=None, max_size=350*1024*1024):
    """Returns positioned temporary file; caller closes it after streaming response."""
    items = list(objects(s3, bucket, f'sessions/{session_id}/' if session_id else 'sessions/'))
    by_session = defaultdict(list)
    for item in items:
        parts = item['Key'].split('/')
        if len(parts) >= 3 and len(parts[1]) == 32 and all(c in '0123456789abcdef' for c in parts[1]):
            by_session[parts[1]].append(item)
    if session_id and session_id not in by_session:
        raise FileNotFoundError('Session not found')
    total_bytes = sum(x.get('Size', 0) for x in items)
    if total_bytes > max_size:
        raise OverflowError('Dataset is too large for one browser export. Use the command-line export instead.')
    f = tempfile.SpooledTemporaryFile(max_size=12*1024*1024)
    try:
        with zipfile.ZipFile(f, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3, allowZip64=True) as z:
            results = []
            for sid, session_items in sorted(by_session.items()):
                results.append(_session_export(z, s3, bucket, sid, session_items))
            z.writestr('study_summary.csv', _csv_content(results))
            z.writestr('README_EXPORT.txt',
                'WebGazer validation study export.\n'
                'csv/ contains flattened raw tables; raw/ preserves original compressed JSON checkpoints.\n'
                'plots/ contains generated descriptive PNG figures, not independently validated eye movements.\n'
                'Study sessions may not represent distinct people (study URL is open and anonymous).\n'
                'Keep the optional names, demographics and raw gaze data in approved protected research storage.\n')
            if not session_id and results:
                good = sum(1 for r in results if r['status']=='submitted')
                statuses = ['Complete','Incomplete or not submitted']
                fig = _png_plot([1,2],[good,len(results)-good], 'Category index (1=complete, 2=other)', 'Sessions',
                                 'Study completion summary', kind='bar')
                if fig: z.writestr('study_plots/completion_overview.png', fig)
        f.seek(0)
        return f
    except BaseException:
        f.close()
        raise
