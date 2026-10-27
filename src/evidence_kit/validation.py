"""Read-only schema and dataset relationship validation."""
import json
import re
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


CHECKER = FormatChecker()


@CHECKER.checks('date-time', raises=(ValueError, OverflowError))
def valid_timestamp(value):
    if not isinstance(value, str):
        return True  # The schema type check owns non-string errors.
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value):
        return False
    datetime.fromisoformat(value.replace('Z', '+00:00'))
    return True


def validators():
    result = {}
    for path in files('evidence_kit').joinpath('schemas/v0.1').iterdir():
        schema = json.loads(path.read_text())
        Draft202012Validator.check_schema(schema)
        result[schema['title']] = Draft202012Validator(schema, format_checker=CHECKER)
    return result


def _time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def validate_records(records):
    """Return actionable errors; never alter or fill in input records.

    Each input is a closed dataset. Exact duplicate IDs are replay-safe;
    conflicting duplicates fail. Incremental store validation belongs to Phase 2.
    """
    errors, by_id, locations = [], {}, {}
    schemas = validators()
    for number, record in enumerate(records, 1):
        prefix = f'record {number}'
        if not isinstance(record, dict):
            errors.append(f'{prefix}: expected an object')
            continue
        typ = record.get('type')
        if not isinstance(typ, str) or typ not in schemas:
            errors.append(f'{prefix}.type: unknown record type {typ!r}')
            continue
        failures = list(schemas[typ].iter_errors(record))
        for error in failures:
            field = '.'.join(str(x) for x in error.absolute_path)
            errors.append(f'{prefix} ({record.get("id", "missing id")}){("." + field) if field else ""}: {error.message}')
        if failures:
            continue
        rid = record['id']
        if rid in by_id:
            if by_id[rid] != record:
                errors.append(f'{prefix}.id: conflicting duplicate {rid!r}')
            continue
        by_id[rid], locations[rid] = record, number
    # Do not cascade relationship errors from schema-invalid input.
    if errors:
        return errors

    def fail(record, field, message):
        errors.append(f'record {locations[record["id"]]} ({record["id"]}).{field}: {message}')

    def ref(record, field, expected, value=None):
        target_id = record[field] if value is None else value
        if target_id is None:
            return None
        target = by_id.get(target_id)
        if target is None or target['type'] not in expected:
            fail(record, field, f'{target_id!r} must reference {" or ".join(expected)} in this dataset')
            return None
        return target

    def contained(record, parent):
        if not (_time(parent['period']['start']) <= _time(record['period']['start']) and _time(record['period']['end']) <= _time(parent['period']['end'])):
            fail(record, 'period', f'must be contained in {parent["id"]!r}')

    refs = {
        'Agreement': {'customer_id': ['Customer']},
        'Workload': {'customer_id': ['Customer']},
        'Execution': {'workload_id': ['Workload']},
        'CostObservation': {'execution_id': ['Execution'], 'supersedes_id': ['CostObservation']},
        'EconomicIntent': {'agreement_id': ['Agreement']},
        'RevenueInput': {'customer_id': ['Customer'], 'agreement_id': ['Agreement']},
        'DriftFinding': {'intent_id': ['EconomicIntent']},
        'Decision': {'recommendation_id': ['Recommendation']},
    }
    attempts, charges, children = {}, {}, {}
    for record in by_id.values():
        typ = record['type']
        for field, expected in refs.get(typ, {}).items():
            if field in record:
                ref(record, field, expected)
        for field, expected in [('finding_ids', ['DriftFinding']), ('evidence_ids', ['CostObservation', 'RevenueInput', 'Execution'])]:
            for target in record.get(field, []):
                ref(record, field, expected, target)
        if 'period' in record and _time(record['period']['start']) >= _time(record['period']['end']):
            fail(record, 'period', 'start must precede end (half-open UTC interval)')
        if typ == 'Execution':
            if _time(record['started_at']) > _time(record['ended_at']):
                fail(record, 'ended_at', 'must not precede started_at')
            key = (record['workload_id'], record['logical_task_id'], record['attempt_id'])
            if key in attempts:
                fail(record, 'attempt_id', f'duplicate logical-task attempt also used by {attempts[key]}')
            attempts[key] = record['id']
        if typ in ('EconomicIntent', 'RevenueInput'):
            agreement = by_id.get(record['agreement_id'])
            if agreement and agreement['type'] == 'Agreement':
                contained(record, agreement)
                if typ == 'EconomicIntent' and record['agreement_version'] != agreement['version']:
                    fail(record, 'agreement_version', 'must match the referenced agreement version')
                if typ == 'RevenueInput' and record['customer_id'] != agreement['customer_id']:
                    fail(record, 'customer_id', 'must match the agreement customer')
        if typ == 'DriftFinding':
            intent = by_id.get(record['intent_id'])
            if intent and intent['type'] == 'EconomicIntent':
                contained(record, intent)
        if typ == 'Decision':
            recommendation = by_id.get(record['recommendation_id'])
            if recommendation and recommendation['type'] == 'Recommendation' and recommendation['status'] == 'HELD' and record['outcome'] == 'approve':
                fail(record, 'outcome', 'a HELD recommendation cannot be approved')
        if typ == 'CostObservation':
            key = (record['source']['system'], record['source']['record_id'], record['component'])
            charges.setdefault(key, []).append(record)
            execution = by_id.get(record['execution_id'])
            if execution and execution['type'] == 'Execution':
                if not (_time(record['period']['start']) <= _time(execution['started_at']) < _time(record['period']['end']) and _time(execution['ended_at']) <= _time(record['period']['end'])):
                    fail(record, 'period', 'must cover the referenced execution')
            previous = by_id.get(record.get('supersedes_id'))
            if previous and previous['type'] == 'CostObservation':
                old_key = (previous['source']['system'], previous['source']['record_id'], previous['component'])
                if old_key != key or previous['execution_id'] != record['execution_id'] or previous['period'] != record['period']:
                    fail(record, 'supersedes_id', 'correction must retain source charge, component, execution, and period')
                if _time(record['observed_at']) <= _time(previous['observed_at']):
                    fail(record, 'observed_at', 'correction must be newer than the superseded observation')
                if previous['id'] in children:
                    fail(record, 'supersedes_id', 'correction chains cannot branch')
                children[previous['id']] = record['id']
    for group in charges.values():
        roots = [r for r in group if 'supersedes_id' not in r]
        if len(roots) != 1:
            fail(group[0], 'source', 'each charge needs one original observation; duplicates require a linear supersedes_id chain')
    return errors


def _reject_constant(value):
    raise ValueError(f'non-finite JSON number {value} is not allowed')


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key {key!r}')
        result[key] = value
    return result


def validate_file(path):
    """Return (record count, errors) for a standalone JSONL dataset."""
    records, lines, errors = [], [], []
    try:
        with Path(path).open(encoding='utf-8') as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line, parse_constant=_reject_constant, object_pairs_hook=_unique_keys))
                    lines.append(line_number)
                except (ValueError, RecursionError) as exc:
                    errors.append(f'line {line_number}: invalid JSON: {exc}')
    except (OSError, UnicodeError) as exc:
        return 0, [str(exc)]
    if not records and not errors:
        errors.append('dataset is empty')
    if not errors:
        for error in validate_records(records):
            number = int(re.match(r'record (\d+)', error).group(1))
            errors.append(f'line {lines[number - 1]}: {error}')
    return len(records), errors
