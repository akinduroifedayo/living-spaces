"""SQLite-only storage visibility and explicit, bounded retention transactions."""
import hashlib
import json
import math

from . import db, limits, records
from .errors import SpacesError

CATEGORIES = ('revisions', 'records', 'logs', 'runs')
# A store-wide token also fences cross-Space blob sharing and delete/recreate.
_TRACKED = ('spaces', 'blobs', 'revisions', 'records', 'changes', 'recovery_points',
            'audit', 'sessions', 'runs', 'upkeep_links', 'refresh_claims',
            'maintenance_spaces', 'maintenance_operations', 'maintenance_effects',
            'maintenance_feeds', 'grants', 'action_intents', 'action_keys', 'bridge_receipts')


def initialize(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS retention_state(id INTEGER PRIMARY KEY CHECK(id=1), nonce TEXT NOT NULL, generation INTEGER NOT NULL)')
    conn.execute('INSERT OR IGNORE INTO retention_state VALUES(1,hex(randomblob(16)),0)')
    for table in _TRACKED:
        for action in ('INSERT', 'UPDATE', 'DELETE'):
            conn.execute(f'''CREATE TRIGGER IF NOT EXISTS retention_{table}_{action} AFTER {action} ON {table}
                BEGIN UPDATE retention_state SET generation=generation+1 WHERE id=1; END''')


def _summary(conn, sid):
    space = db.space(conn, sid)
    category = {}
    for name, table, payload in (
        ('revisions', 'revisions', 'length(CAST(manifest AS BLOB))+length(CAST(files AS BLOB))+length(CAST(summary AS BLOB))'),
        ('records', 'records', 'length(CAST(data AS BLOB))'),
        ('source_entries', 'records', 'coalesce(length(CAST(source AS BLOB)),0)+coalesce(length(CAST(source_meta AS BLOB)),0)'),
        ('logs', 'logs', 'length(CAST(msg AS BLOB))'),
        ('runs', 'runs', 'length(CAST(detail AS BLOB))+length(CAST(changed AS BLOB))+coalesce(length(CAST(error AS BLOB)),0)'),
        ('recovery_points', 'recovery_points', 'length(CAST(snapshot AS BLOB))'),
        ('audit', 'audit', 'length(CAST(detail AS BLOB))'),
        ('changes', 'changes', 'length(CAST(collection AS BLOB))+length(CAST(record_id AS BLOB))'),
    ):
        condition = ' AND source IS NOT NULL' if name == 'source_entries' else ''
        category[name] = dict(conn.execute(f'SELECT count(*) AS count,coalesce(sum({payload}),0) AS bytes FROM {table} WHERE space=?{condition}', (sid,)).fetchone())
    category['blobs'] = dict(conn.execute('''SELECT count(*) AS count,coalesce(sum(size),0) AS bytes FROM blobs
        WHERE sha IN (SELECT f.value FROM revisions r,json_each(r.files) f WHERE r.space=?)''', (sid,)).fetchone())
    category['source_entries']['fields'] = conn.execute('''SELECT count(*) FROM records r,json_each(r.source)
        WHERE r.space=? AND r.source IS NOT NULL''', (sid,)).fetchone()[0]
    category['runs']['source_details'] = conn.execute('''SELECT count(*) FROM runs r,json_each(r.detail,'$.sources')
        WHERE r.space=?''', (sid,)).fetchone()[0]
    head = conn.execute('''SELECT count(*) AS files,coalesce(sum(b.size),0) AS bytes,coalesce(max(b.size),0) AS largest
        FROM revisions r,json_each(r.files) f JOIN blobs b ON b.sha=f.value WHERE r.space=? AND r.rev=?''',
        (sid, space['head_rev'])).fetchone()
    record = conn.execute('''SELECT coalesce(max(length(CAST(data AS BLOB))),0) AS data,
        coalesce(max(length(CAST(source AS BLOB))),0) AS source,
        coalesce(max(length(CAST(source_meta AS BLOB))),0) AS metadata FROM records WHERE space=?''', (sid,)).fetchone()
    resources = [
        ('project_bytes', head['bytes'], limits.PROJECT_BYTES),
        ('project_files', head['files'], limits.PROJECT_FILES),
        ('file_bytes', head['largest'], limits.FILE_BYTES),
        ('records', category['records']['count'], limits.RECORDS),
        ('data_bytes', record['data'], limits.DATA_BYTES),
        ('source_bytes', record['source'], limits.SOURCE_BYTES),
        ('source_metadata_bytes', record['metadata'], limits.SOURCE_BYTES),
    ]
    usage = [limits.usage(resource, used, maximum) for resource, used, maximum in resources]
    # logs.py trims log history to its newest entries, so a full history never stops a write.
    usage.append({'resource': 'log_history', 'used': category['logs']['count'], 'limit': limits.LOG_HISTORY, 'approaching': False})
    return {'categories': category, 'limits': usage, 'warnings': [row for row in usage if row['approaching']],
            'bytes_basis': 'Logical UTF-8 payload bytes; excludes SQLite overhead. Shared blobs count once per Space.',
            'native_history': {'ownership': 'native-owned', 'counted': False, 'deletable': False}}


def storage_summary(sid):
    with db.read() as conn:
        return _summary(conn, sid)


def _scope(scope):
    limits.object_json(scope)
    if set(scope) != {'categories', 'before'}:
        raise SpacesError('invalid', 'Retention scope requires categories and before')
    categories, before = scope['categories'], scope['before']
    if (not isinstance(categories, list) or not categories or len(categories) > len(CATEGORIES)
            or any(not isinstance(name, str) or name not in CATEGORIES for name in categories)
            or len(set(categories)) != len(categories)):
        raise SpacesError('invalid', 'Unknown or duplicate retention category')
    if type(before) not in (int, float) or not math.isfinite(before) or before < 0:
        raise SpacesError('invalid', 'Retention before must be a finite nonnegative timestamp')
    return {'categories': sorted(categories), 'before': before}


# Preserve the exact rows that supply Q15 freshness, including success before a failed attempt.
_FRESH_RUNS = '''WITH sources AS (
    SELECT r.id,r.rowid AS position,r.queued_at,r.ended_at,j.key AS source_index,
      json_extract(j.value,'$.id') AS source,
      coalesce(json_extract(j.value,'$.last_attempt_at'),r.started_at,r.queued_at) AS attempt,
      CASE WHEN json_extract(j.value,'$.ok')=1 THEN
        coalesce(json_extract(j.value,'$.last_success_at'),r.ended_at) END AS success
    FROM runs r,json_each(r.detail,'$.sources') j WHERE r.space=? AND r.handler='feed'
  ), ranked AS (
    SELECT *,row_number() OVER (PARTITION BY source ORDER BY attempt DESC,position DESC,CAST(source_index AS INTEGER) DESC) AS latest,
      row_number() OVER (PARTITION BY source ORDER BY success DESC,position DESC,CAST(source_index AS INTEGER) DESC) AS good
    FROM sources
  ) SELECT id FROM ranked WHERE latest=1 OR (good=1 AND success IS NOT NULL)
  UNION SELECT id FROM (SELECT id FROM runs WHERE space=? ORDER BY queued_at DESC,rowid DESC LIMIT 1)
  UNION SELECT id FROM (SELECT id FROM runs WHERE space=? AND status='succeeded' ORDER BY ended_at DESC LIMIT 1)'''


def _proposal(conn, sid, scope):
    space = db.space(conn, sid)
    state = dict(conn.execute('SELECT nonce,generation FROM retention_state WHERE id=1').fetchone())
    state['schema'] = conn.execute('PRAGMA schema_version').fetchone()[0]
    pending = bool(conn.execute('''SELECT 1 FROM runs WHERE space=? AND status IN ('queued','running')
        UNION ALL SELECT 1 FROM refresh_claims WHERE space=?
        UNION ALL SELECT 1 FROM maintenance_operations WHERE space=? AND phase!='retired' LIMIT 1''', (sid, sid, sid)).fetchone())
    remove = {name: [] for name in (*CATEGORIES, 'source_entries', 'blobs')}
    protected = {name: [] for name in (*CATEGORIES, 'source_entries', 'blobs')}
    truncated = []
    for name in scope['categories']:
        if name == 'revisions':
            sql = '''SELECT rev,files,
                CASE WHEN rev=? THEN 'head revision'
                  WHEN EXISTS(SELECT 1 FROM recovery_points p WHERE p.space=r.space AND p.head_rev=r.rev) THEN 'recovery point'
                  WHEN EXISTS(SELECT 1 FROM sessions s WHERE s.space=r.space AND s.head_rev=r.rev AND s.closed_at IS NULL) THEN 'open session'
                  WHEN json_array_length(manifest,'$.data.migrations')>0 THEN 'migration'
                  WHEN EXISTS(SELECT 1 FROM revisions restored WHERE restored.space=r.space AND restored.restored_from=r.rev) THEN 'restore reference'
                  WHEN EXISTS(SELECT 1 FROM audit a,json_tree(a.detail) j WHERE a.space=r.space
                    AND j.key IN ('rev','revision','head_rev','base_rev','from_rev','to_rev','restored_from') AND j.value=r.rev) THEN 'audit reference'
                END AS reason FROM revisions r WHERE space=? AND created_at<?'''
            args, order = (space['head_rev'], sid, scope['before']), 'rev'
        elif name == 'records':
            sql = '''SELECT collection,id,rev,source IS NOT NULL AS source_entry,
                (SELECT count(*) FROM json_each(source)) AS fields,
                CASE WHEN json(data)!='{}' THEN 'user data' WHEN source IS NULL THEN 'user-authored record' END AS reason
                FROM records WHERE space=? AND updated_at<?'''
            args, order = (sid, scope['before']), 'collection,id'
        elif name == 'runs':
            sql = f'''SELECT id,queued_at,rowid,coalesce(json_array_length(detail,'$.sources'),0) AS source_details, CASE WHEN status IN ('queued','running') THEN 'pending run'
                WHEN handler='agent' THEN 'native-owned'
                WHEN id IN ({_FRESH_RUNS}) THEN 'freshness reference' END AS reason
                FROM runs WHERE space=? AND queued_at<?'''
            args, order = (sid, sid, sid, sid, scope['before']), 'queued_at,rowid'
        else:
            sql = 'SELECT id,NULL AS reason FROM logs WHERE space=? AND at<?'
            args, order = (sid, scope['before']), 'id'
        rows = conn.execute(f"""WITH candidates AS ({sql}), protection AS (
            SELECT *,CASE WHEN ? THEN 'pending work' ELSE reason END AS kept_reason FROM candidates
          ), ranked AS (
            SELECT *,row_number() OVER (PARTITION BY kept_reason IS NULL ORDER BY {order}) AS position FROM protection
          ) SELECT * FROM ranked WHERE position<=? ORDER BY {order}""", (*args, pending, limits.BATCH_OPS + 1)).fetchall()
        for row in rows:
            if row['position'] > limits.BATCH_OPS:
                if name not in truncated:
                    truncated.append(name)
                continue
            item = {key: row[key] for key in row.keys() if key not in (
                'reason', 'kept_reason', 'position', 'files', 'source_entry', 'fields', 'queued_at', 'rowid')}
            reason = row['kept_reason']
            target = protected if reason else remove
            target[name].append({**item, 'reason': reason} if reason else item)
            if name == 'records' and row['source_entry']:
                source = {'collection': row['collection'], 'id': row['id'], 'fields': row['fields']}
                target['source_entries'].append({**source, 'reason': reason} if reason else source)
    # Only blobs of removed revisions are candidates. Shared or retained references always win.
    revs = [row['rev'] for row in remove['revisions']]
    if revs:
        marks = ','.join('?' for _ in revs)
        blobs = conn.execute(f'''SELECT sha,size,EXISTS(
            SELECT 1 FROM revisions r,json_each(r.files) f WHERE f.value=b.sha AND NOT(r.space=? AND r.rev IN ({marks}))) AS retained
            FROM blobs b WHERE sha IN (SELECT f.value FROM revisions r,json_each(r.files) f
                WHERE r.space=? AND r.rev IN ({marks})) ORDER BY sha''', (sid, *revs, sid, *revs))
        for row in blobs:
            item = {'sha': row['sha'], 'bytes': row['size']}
            (protected if row['retained'] else remove)['blobs'].append(
                {**item, 'reason': 'retained or shared revision'} if row['retained'] else item)
    proposal = {'space': sid, 'scope': scope, 'remove': remove, 'protected': protected, 'truncated': truncated,
                'batch_limit_per_category': limits.BATCH_OPS, 'native_history': 'native-owned; excluded'}
    encoded = limits.dumps({'state': state, 'proposal': proposal})
    proposal['id'] = 'q18-' + hashlib.sha256(encoded.encode()).hexdigest()
    proposal['confirmation'] = f"delete {sid} {proposal['id']}"
    return proposal


def propose_retention(sid, scope):
    scope = _scope(scope)
    with db.read() as conn:
        return _proposal(conn, sid, scope)


def execute_retention(sid, *, scope, proposal_id, confirm, actor):
    scope = _scope(scope)
    limits.text(proposal_id, 'proposal_id')
    limits.text(actor, 'actor')
    if confirm != f'delete {sid} {proposal_id}':
        raise SpacesError('invalid', 'Retention confirmation must name this Space and exact proposal')
    with db.write() as conn:
        proposal = _proposal(conn, sid, scope)
        if proposal['id'] != proposal_id:
            raise SpacesError('conflict', 'Retention proposal is stale; preview again')
        removed = {name: 0 for name in proposal['remove']}
        removed['source_entries'] = len(proposal['remove']['source_entries'])
        removed['source_fields'] = sum(row['fields'] for row in proposal['remove']['source_entries'])
        removed['source_details'] = sum(row['source_details'] for row in proposal['remove']['runs'])
        for item in proposal['remove']['records']:
            records._delete(conn, sid, item['collection'], item['id'], actor=actor, base_rev=item['rev'])
            removed['records'] += 1
        for item in proposal['remove']['revisions']:
            removed['revisions'] += conn.execute('DELETE FROM revisions WHERE space=? AND rev=?', (sid, item['rev'])).rowcount
        for name in ('logs', 'runs'):
            for item in proposal['remove'][name]:
                removed[name] += conn.execute(f'DELETE FROM {name} WHERE space=? AND id=?', (sid, item['id'])).rowcount
        for item in proposal['remove']['blobs']:
            removed['blobs'] += conn.execute('DELETE FROM blobs WHERE sha=?', (item['sha'],)).rowcount
        receipt = {'proposal_id': proposal_id, 'scope': scope, 'removed': removed, 'items': proposal['remove']}
        # This controlled receipt contains identifiers/counts only, no user payload or secrets.
        receipt['audit_id'] = conn.execute('''INSERT INTO audit(space,at,actor,action,outcome,detail)
            VALUES(?,?,?,'retention','succeeded',?)''', (sid, db.now(), actor, limits.dumps(receipt))).lastrowid
        return receipt
