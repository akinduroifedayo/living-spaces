"""Private, bounded unsaved drafts. The profile is the owning database, never a guest argument."""
import json

from . import db, grants, limits, sessions
from .errors import SpacesError

MAX_COUNT = 100
MAX_BYTES = 1024 * 1024
MAX_ENTRY_BYTES = 64 * 1024
TTL_SECONDS = 7 * 24 * 60 * 60


def key(editor, schema, collection, id):
    for value, label in ((editor, 'record'), (collection, 'collection'), (id, 'record')):
        limits.identifier(value, label)
    limits.integer(schema, 'draft schema', minimum=1)
    return editor, schema, collection, id


def _delete(conn, sid, editor, schema, collection, id):
    conn.execute('DELETE FROM editor_drafts WHERE space=? AND editor=? AND schema=? AND collection=? AND record_id=?',
                 (sid, *key(editor, schema, collection, id)))


def _prune(conn):
    conn.execute('DELETE FROM editor_drafts WHERE expires_at<=?', (db.now(),))
    rows = conn.execute('SELECT space,editor,schema,collection,record_id,bytes FROM editor_drafts '
                        'ORDER BY updated_at,space,editor,schema,collection,record_id').fetchall()
    count, size = len(rows), sum(row['bytes'] for row in rows)
    for row in rows:
        if count <= MAX_COUNT and size <= MAX_BYTES:
            break
        _delete(conn, row['space'], row['editor'], row['schema'], row['collection'], row['record_id'])
        count -= 1
        size -= row['bytes']


def call(sid, session, operation, *, editor, schema, collection, id, draft=None):
    identity = key(editor, schema, collection, id)
    encoded = limits.object_json(draft, MAX_ENTRY_BYTES, 'draft') if operation == 'put' else None
    with db.write() as conn:
        sessions._require(conn, sid, session)
        space = db.space(conn, sid, writable=True)
        if not grants._check(conn, sid, 'data'):
            raise SpacesError('not_granted', 'Data access is off', capability='data')
        _prune(conn)
        conn.execute('DELETE FROM editor_drafts WHERE space=? AND data_version<>?', (sid, space['data_version']))
        if operation == 'put':
            at = db.now()
            conn.execute('INSERT OR REPLACE INTO editor_drafts '
                         '(space,editor,schema,collection,record_id,data_version,payload,bytes,updated_at,expires_at) '
                         'VALUES(?,?,?,?,?,?,?,?,?,?)',
                         (sid, *identity, space['data_version'], encoded, len(encoded.encode('utf-8')), at, at + TTL_SECONDS))
            _prune(conn)
        elif operation == 'delete':
            _delete(conn, sid, *identity)
        row = conn.execute('SELECT payload FROM editor_drafts WHERE space=? AND editor=? AND schema=? '
                           'AND collection=? AND record_id=?', (sid, *identity)).fetchone()
        return {'draft': json.loads(row['payload']) if row else None, 'recovery': 'durable'}
