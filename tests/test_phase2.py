import copy
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from evidence_kit.reporting import economic_report
from evidence_kit.storage import read_jsonl, read_store, replay

ROOT = Path(__file__).resolve().parents[1]


def fixture(name='healthy'):
    return read_jsonl([ROOT / 'examples' / f'{name}.jsonl'])


def get(rows, typ):
    return next(r for r in rows if r['type'] == typ)


def report(rows, **kwargs):
    return economic_report(rows, 'intent-1', coverage_source='Synthetic fixture declared complete', **kwargs)


def codes(result):
    return {i['code'] for i in result['issues']}


@pytest.mark.parametrize('name,cost,margin,successes,unit_cost', [
    ('healthy', '10', '90', 1, '10'),
    ('retry-drift', '45', '55', 1, '45'),
    ('model-change', '45', '55', 2, '22.5'),
])
def test_fixture_arithmetic_and_replay(tmp_path, name, cost, margin, successes, unit_cost):
    rows = fixture(name); db = tmp_path / 'evidence.sqlite'
    first = replay(db, rows)
    before = report(read_store(db))
    second = replay(db, rows)
    assert first['inserted'] == len(rows) and second['inserted'] == 0
    assert second['duplicates'] == len(rows)
    assert report(read_store(db)) == before
    assert Decimal(before['service_cost']) == Decimal(cost)
    assert Decimal(before['margin_amount']) == Decimal(margin)
    assert Decimal(before['margin_percent']) == Decimal(margin)
    assert Decimal(before['cost_per_successful_task']) == Decimal(unit_cost)
    assert before['successful_tasks'] == successes
    assert before['issues'] == []


def test_missing_attribution():
    result = report(fixture('missing-attribution'))
    assert Decimal(result['observed_cost_subtotal']) == 10
    assert Decimal(result['unallocated']['observed_subtotal']) == 5
    assert result['unknown_cost_ids'] == ['cost-unknown']
    assert result['service_cost'] is None and result['margin_percent'] is None
    assert {'UNKNOWN_COST', 'UNALLOCATED_COST'} <= codes(result)


def test_coverage_not_inferred():
    result = economic_report(fixture(), 'intent-1')
    assert result['service_cost'] is None
    assert 'COST_COVERAGE_UNDECLARED' in codes(result)
    assert result['observed_cost_subtotal'] == '10.00'


def test_batch_rollback_and_incremental_reference(tmp_path):
    db = tmp_path / 'store.sqlite'; rows = fixture(); replay(db, rows)
    conflict = dict(rows[0], name='conflicting')
    with pytest.raises(ValueError, match='conflicting duplicate'):
        replay(db, [dict(rows[0], id='new-customer'), conflict])
    assert read_store(db) == sorted(rows, key=lambda r: r['id'])
    with pytest.raises(ValueError, match='must reference'):
        replay(db, [dict(get(rows, 'Execution'), id='new-exec', workload_id='absent')])
    cost = dict(get(rows, 'CostObservation'), id='correction', supersedes_id='cost-1', observed_at='2026-10-03T00:00:00Z', amount='12.00')
    assert replay(db, [cost])['inserted'] == 1
    result = report(read_store(db), as_of='2026-10-03T00:00:00Z')
    assert Decimal(result['service_cost']) == 12
    assert [r['id'] for r in result['cost_evidence']] == ['correction']
    assert len(read_store(db)) == len(rows) + 1
    assert replay(db, rows)['inserted'] == 0  # Original replay cannot resurrect old charge.


def test_unknown_customer_is_unallocated():
    rows = fixture(); get(rows, 'Workload')['customer_id'] = None
    result = report(rows)
    assert result['service_cost'] is None
    assert Decimal(result['unallocated']['observed_subtotal']) == 10


def test_missing_execution_cost():
    rows = [r for r in fixture() if r['type'] != 'CostObservation']
    result = report(rows)
    assert 'MISSING_EXECUTION_COST' in codes(result)
    assert result['service_cost'] is None


def test_estimate_freshness_and_no_blending():
    rows = fixture(); cost = get(rows, 'CostObservation')
    cost.update(status='estimated', estimate_method='token-price', pricing_version='v1')
    fresh = report(rows)
    assert fresh['observed_cost_subtotal'] == '0'
    assert fresh['estimated_cost_subtotal'] == '10.00'
    assert fresh['service_cost'] is None
    assert 'STALE_ESTIMATE' not in codes(fresh)
    stale = report(rows, as_of='2026-10-04T00:00:00Z')
    assert {'ESTIMATED_COST', 'STALE_ESTIMATE'} <= codes(stale)


def test_future_observation():
    rows = fixture(); get(rows, 'CostObservation')['observed_at'] = '2026-10-05T00:00:00Z'
    result = report(rows)
    assert 'OBSERVATION_AFTER_AS_OF' in codes(result)
    assert result['service_cost'] is None


@pytest.mark.parametrize('mode,code', [('missing', 'MISSING_REVENUE'), ('partial', 'INCOMPLETE_REVENUE'), ('unknown', 'INCOMPLETE_REVENUE'), ('period', 'REVENUE_PERIOD_MISMATCH'), ('duplicate', 'AMBIGUOUS_REVENUE')])
def test_revenue_gaps(mode, code):
    rows = fixture(); revenue = get(rows, 'RevenueInput')
    if mode == 'missing': rows.remove(revenue)
    if mode == 'partial': revenue['completeness'] = 'partial'
    if mode == 'unknown': revenue.update(completeness='unknown', amount=None, reason='Missing invoice')
    if mode == 'period': revenue['period']['end'] = '2026-10-01T12:00:00Z'
    if mode == 'duplicate': rows.append(dict(revenue, id='revenue-copy'))
    result = report(rows)
    assert result['margin_amount'] is None and result['revenue'] is None
    assert Decimal(result['service_cost']) == 10
    assert code in codes(result)


def test_zero_denominators():
    rows = fixture(); get(rows, 'RevenueInput')['amount'] = '0.00'
    get(rows, 'Execution')['status'] = 'failed'
    result = report(rows)
    assert result['margin_amount'] == '-10.00'
    assert result['margin_percent'] is None and result['cost_per_successful_task'] is None
    assert {'ZERO_REVENUE', 'NO_SUCCESSFUL_TASKS'} <= codes(result)


def test_cost_period_not_prorated():
    rows = fixture(); get(rows, 'CostObservation')['period']['end'] = '2026-10-03T00:00:00Z'
    result = report(rows)
    assert result['service_cost'] is None
    assert result['incompatible_cost_ids'] == ['cost-1']
    assert 'COST_PERIOD_MISMATCH' in codes(result)


def test_other_customer_costs_excluded():
    rows = fixture()
    rows.extend([dict(get(rows, 'Customer'), id='other-customer'), dict(get(rows, 'Workload'), id='other-workload', customer_id='other-customer'), dict(get(rows, 'Execution'), id='other-exec', workload_id='other-workload')])
    cost = copy.deepcopy(get(rows, 'CostObservation')); cost.update(id='other-cost', execution_id='other-exec', amount='999.00'); cost['source']['record_id'] = 'other-charge'; rows.append(cost)
    assert Decimal(report(rows)['service_cost']) == 10


def test_decimal_precision_and_scope():
    rows = fixture(); get(rows, 'CostObservation')['amount'] = '0.10000001'
    other = copy.deepcopy(get(rows, 'CostObservation')); other.update(id='storage-cost', component='storage', amount='999.00'); rows.append(other)
    result = report(rows)
    assert result['service_cost'] == '0.10000001'
    assert result['margin_amount'] == '99.89999999'


def test_successful_retries_count_once():
    rows = fixture('retry-drift')
    for r in rows:
        if r['type'] == 'Execution': r['status'] = 'succeeded'
    assert report(rows)['successful_tasks'] == 1


def test_read_missing_db_does_not_create(tmp_path):
    path = tmp_path / 'absent.sqlite'
    with pytest.raises(sqlite3.OperationalError): read_store(path)
    assert not path.exists()


def test_cli_replay_report_and_errors(tmp_path):
    db = str(tmp_path / 'cli.sqlite'); base = [sys.executable, '-m', 'evidence_kit']
    ingest = subprocess.run(base + ['replay', '--db', db, str(ROOT/'examples/healthy.jsonl')], capture_output=True, text=True)
    assert ingest.returncode == 0 and json.loads(ingest.stdout)['inserted'] == 7
    output = subprocess.run(base + ['report', '--db', db, '--intent', 'intent-1', '--coverage-source', 'Synthetic fixture'], capture_output=True, text=True)
    assert output.returncode == 0 and Decimal(json.loads(output.stdout)['service_cost']) == 10
    bad = subprocess.run(base + ['report', '--db', db, '--intent', 'absent'], capture_output=True, text=True)
    assert bad.returncode == 1 and 'error' in json.loads(bad.stderr)
    assert 'Traceback' not in bad.stderr


def test_report_input_unchanged_and_deterministic():
    rows = fixture(); before = copy.deepcopy(rows)
    assert report(rows) == report(list(reversed(rows)))
    assert rows == before


def test_failed_new_batch_leaves_no_records(tmp_path):
    db = tmp_path / 'atomic.sqlite'; rows = fixture()
    rows.append(dict(rows[0], name='conflict'))
    with pytest.raises(ValueError): replay(db, rows)
    # The transaction rolls back creation of the evidence table as well.
    with sqlite3.connect(db) as connection:
        assert not connection.execute("SELECT name FROM sqlite_master WHERE name='evidence_records'").fetchall()


def test_partial_files_share_reference_context(tmp_path):
    rows = fixture(); db = tmp_path/'parts.sqlite'
    replay(db, rows[:5])
    assert replay(db, rows[5:])['inserted'] == 2
    assert report(read_store(db))['service_cost'] == '10.00'


def test_missing_component_and_zero_cost():
    rows = fixture(); get(rows, 'EconomicIntent')['cost_scope'].append('storage')
    assert 'MISSING_EXECUTION_COST' in codes(report(rows))
    storage = dict(get(rows, 'CostObservation'), id='zero-storage', component='storage', amount='0.00')
    rows.append(storage)
    assert report(rows)['service_cost'] == '10.00'


def test_invalid_report_settings():
    with pytest.raises(ValueError): report(fixture(), as_of='not-a-date')
    with pytest.raises(ValueError): report(fixture(), as_of='2026-10-01T00:00:00Z')
    with pytest.raises(ValueError): report(fixture(), max_estimate_age_hours=-1)
    with pytest.raises(ValueError): economic_report(fixture(), 'intent-1', coverage_source=' ')


def test_large_decimal_precision():
    rows = fixture(); get(rows, 'CostObservation')['amount'] = '123456789012345678901234567890.12345678'
    result = report(rows)
    assert result['service_cost'] == '123456789012345678901234567890.12345678'
    assert result['margin_amount'] == '-123456789012345678901234567790.12345678'


def test_no_cross_period_cost_allocation():
    rows = fixture()
    old = dict(get(rows, 'CostObservation'), id='old-unallocated', execution_id=None, period={'start':'2026-09-01T00:00:00Z','end':'2026-10-01T00:00:00Z'}, source={'system':'meter','record_id':'old'})
    rows.append(old)
    assert report(rows)['issues'] == []
