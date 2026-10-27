"""Transactional, immutable local evidence storage."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from .validation import _reject_constant, _unique_keys, validate_records


def read_jsonl(paths):
    records = []
    for path in paths:
        count = 0
        with Path(path).open(encoding='utf-8') as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line, parse_constant=_reject_constant, object_pairs_hook=_unique_keys))
                except (ValueError, RecursionError) as exc:
                    raise ValueError(f'{path}: line {line_number}: {exc}') from exc
                count += 1
        if not count:
            raise ValueError(f'{path}: empty dataset')
    return records


def _read(connection):
    return [json.loads(row[0]) for row in connection.execute('SELECT payload FROM evidence_records ORDER BY id')]


def replay(database, records):
    """Validate existing + incoming evidence under a write lock, then commit all or none."""
    if not records:
        raise ValueError('empty replay batch')
    with closing(sqlite3.connect(database, timeout=30)) as connection:
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('CREATE TABLE IF NOT EXISTS evidence_records (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            existing = _read(connection)
            errors = validate_records(existing + records)
            if errors:
                raise ValueError('batch rejected (records include existing store, then incoming batch):\n' + '\n'.join(errors))
            old_ids = {r['id'] for r in existing}
            inserted = 0
            for record in records:
                if record['id'] in old_ids:
                    continue
                connection.execute('INSERT INTO evidence_records VALUES (?, ?)', (record['id'], json.dumps(record, sort_keys=True, allow_nan=False)))
                old_ids.add(record['id'])
                inserted += 1
            return {'received': len(records), 'inserted': inserted, 'duplicates': len(records) - inserted, 'stored': len(old_ids)}


def read_store(database):
    """Open read-only: reporting must never create a missing database."""
    uri = Path(database).resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        records = _read(connection)
    errors = validate_records(records)
    if errors:
        raise ValueError('stored evidence is invalid:\n' + '\n'.join(errors))
    return records
