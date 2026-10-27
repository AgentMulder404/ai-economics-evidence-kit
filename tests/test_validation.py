import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from evidence_kit.validation import validate_file, validate_records, validators

ROOT = Path(__file__).resolve().parents[1]


def fixture(name='healthy'):
    return [json.loads(line) for line in (ROOT / 'examples' / f'{name}.jsonl').read_text().splitlines()]


def entity(rows, typ):
    return next(r for r in rows if r['type'] == typ)


@pytest.mark.parametrize('name', ['healthy', 'retry-drift', 'model-change', 'missing-attribution'])
def test_scenarios(name):
    rows = fixture(name)
    before = copy.deepcopy(rows)
    assert validate_records(rows) == []
    assert rows == before


@pytest.mark.parametrize('typ,field,value,expected', [
    ('CostObservation', 'amount', 1.25, 'amount'),
    ('CostObservation', 'amount', '-1.00', 'amount'),
    ('CostObservation', 'amount', 'NaN', 'amount'),
    ('CostObservation', 'amount', '1e3', 'amount'),
    ('CostObservation', 'amount', None, 'amount'),
    ('CostObservation', 'currency', 'EUR', 'currency'),
    ('CostObservation', 'execution_id', 'absent', 'must reference'),
    ('CostObservation', 'execution_id', 'customer-1', 'must reference'),
    ('CostObservation', 'status', 'estimated', 'estimate_method'),
    ('CostObservation', 'observed_at', '2026-02-30T00:00:00Z', 'date-time'),
    ('CostObservation', 'observed_at', '2026-10-01T00:00:00+00:00', 'Z$'),
    ('EconomicIntent', 'agreement_version', '2', 'agreement version'),
    ('EconomicIntent', 'quality_floor', 2, 'maximum'),
    ('Execution', 'ended_at', '2026-09-01T00:00:00Z', 'must not precede'),
    ('Customer', 'schema_version', '9', '0.1'),
    ('Customer', 'id', '', 'does not match'),
    ('Customer', 'type', [], 'unknown record type'),
])
def test_invalid_fields(typ, field, value, expected):
    rows = fixture()
    entity(rows, typ)[field] = value
    assert expected in '\n'.join(validate_records(rows))


def test_missing_id_and_unknown_field():
    rows = fixture()
    del rows[0]['id']
    rows[0]['secret'] = 'not accepted'
    errors = '\n'.join(validate_records(rows))
    assert "'id' is a required property" in errors
    assert 'Additional properties' in errors


def test_unknown_is_not_zero():
    rows = fixture('missing-attribution')
    unknown = next(r for r in rows if r.get('status') == 'unknown')
    assert not validate_records(rows)
    assert unknown['amount'] is None
    unknown['amount'] = '0.00'
    assert validate_records(rows)
    unknown['amount'] = None
    del unknown['reason']
    assert 'reason' in '\n'.join(validate_records(rows))


def test_estimate_requires_provenance():
    rows = fixture()
    cost = entity(rows, 'CostObservation')
    cost.update(status='estimated', estimate_method='tokens times unit price', pricing_version='2026-10')
    assert not validate_records(rows)


def test_duplicate_replay_and_conflict():
    rows = fixture()
    assert not validate_records(rows + copy.deepcopy(rows))
    changed = copy.deepcopy(rows[0]); changed['name'] = 'changed'
    assert 'conflicting duplicate' in '\n'.join(validate_records(rows + [changed]))


def test_duplicate_charge_requires_correction():
    rows = fixture()
    cost = copy.deepcopy(entity(rows, 'CostObservation')); cost['id'] = 'cost-copy'
    assert 'duplicates require' in '\n'.join(validate_records(rows + [cost]))
    cost.update(supersedes_id='cost-1', observed_at='2026-10-03T00:00:00Z', amount='12.00')
    assert not validate_records(rows + [cost])
    cost['supersedes_id'] = cost['id']
    assert validate_records(rows + [cost])


def test_correction_branch_rejected():
    rows = fixture()
    base = entity(rows, 'CostObservation')
    for i in [2, 3]:
        rows.append(dict(base, id=f'correction-{i}', supersedes_id='cost-1', observed_at=f'2026-10-0{i+1}T00:00:00Z'))
    assert 'cannot branch' in '\n'.join(validate_records(rows))


def test_customer_mismatch():
    rows = fixture()
    rows.append(dict(rows[0], id='customer-2'))
    entity(rows, 'RevenueInput')['customer_id'] = 'customer-2'
    assert 'agreement customer' in '\n'.join(validate_records(rows))


def test_invalid_periods():
    rows = fixture()
    entity(rows, 'EconomicIntent')['period']['end'] = '2026-10-03T00:00:00Z'
    assert 'contained' in '\n'.join(validate_records(rows))
    rows = fixture()
    entity(rows, 'Agreement')['period']['end'] = '2026-09-01T00:00:00Z'
    assert 'start must precede' in '\n'.join(validate_records(rows))


def governance():
    rows = fixture('retry-drift')
    common = {'schema_version': '0.1'}
    rows.extend([
        dict(common, type='DriftFinding', id='finding-1', intent_id='intent-1', period=copy.deepcopy(rows[1]['period']), observed_result='45.00', threshold='20.00', metric='service_cost', unit='USD', evidence_ids=['cost-1','cost-2','cost-3'], rule_version='budget/0.1', reason_codes=['OVER_BUDGET']),
        dict(common, type='Recommendation', id='recommendation-1', finding_ids=['finding-1'], proposed_action='review retry policy', rationale='Costs exceed budget', evidence_ids=['cost-1','cost-2','cost-3'], policy_version='0.1', status='READY', hold_reasons=[]),
        dict(common, type='Decision', id='decision-1', recommendation_id='recommendation-1', outcome='approve', actor='synthetic-reviewer', decided_at='2026-10-03T00:00:00Z', rationale='Review warranted'),
    ])
    return rows


def test_governance_contract():
    rows = governance()
    assert not validate_records(rows)
    rec = entity(rows, 'Recommendation')
    rec.update(status='HELD', hold_reasons=['MISSING_EVIDENCE'])
    assert 'cannot be approved' in '\n'.join(validate_records(rows))
    entity(rows, 'Decision')['outcome'] = 'reject'
    assert not validate_records(rows)
    rec['hold_reasons'] = []
    assert validate_records(rows)


def test_governance_evidence_references():
    rows = governance()
    entity(rows, 'DriftFinding')['evidence_ids'] = ['customer-1']
    assert 'must reference' in '\n'.join(validate_records(rows))


def test_all_schemas_load():
    assert len(validators()) == 10


@pytest.mark.parametrize('content,expected', [('', 'empty'), ('{bad}\n', 'line 1'), ('[]\n', 'expected an object')])
def test_bad_files(tmp_path, content, expected):
    path = tmp_path / 'bad.jsonl'; path.write_text(content)
    assert expected in '\n'.join(validate_file(path)[1])


def test_cli_errors_and_machine_output(tmp_path):
    missing = tmp_path / 'missing.jsonl'
    command = [sys.executable, '-m', 'evidence_kit', 'validate', '--json']
    result = subprocess.run(command + [str(ROOT/'examples/healthy.jsonl'), str(missing)], capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report[0]['valid'] and not report[1]['valid']
    assert 'Traceback' not in result.stderr


def test_line_numbers_include_blank_lines(tmp_path):
    path = tmp_path / 'bad.jsonl'; path.write_text('\n{}\n')
    assert validate_file(path)[1][0].startswith('line 2:')


@pytest.mark.parametrize('content,expected', [('{"x": NaN}', 'non-finite'), ('{"x":1,"x":2}', 'duplicate JSON key')])
def test_ambiguous_json_rejected(tmp_path, content, expected):
    path = tmp_path / 'ambiguous.jsonl'; path.write_text(content)
    assert expected in '\n'.join(validate_file(path)[1])


def test_duplicate_attempt_rejected():
    rows = fixture()
    execution = dict(entity(rows, 'Execution'), id='exec-duplicate')
    assert 'duplicate logical-task attempt' in '\n'.join(validate_records(rows + [execution]))


def test_unknown_customer_and_revenue():
    rows = fixture()
    entity(rows, 'Workload')['customer_id'] = None
    revenue = entity(rows, 'RevenueInput')
    revenue.update(completeness='unknown', amount=None, reason='Billing export missing')
    assert not validate_records(rows)
    revenue['amount'] = '0.00'
    assert validate_records(rows)
