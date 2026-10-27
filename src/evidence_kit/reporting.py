"""Deterministic, scope-aware economic evidence reports; no policy decisions."""
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

from .validation import _time, valid_timestamp, validate_records


def _bounds(period):
    return _time(period['start']), _time(period['end'])


def _overlap(a, b):
    return a[0] < b[1] and b[0] < a[1]


def _money(value):
    return None if value is None else format(value, 'f')


def _ratio(numerator, denominator):
    return _money((numerator / denominator).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_EVEN))


def economic_report(records, intent_id, *, coverage_source=None, as_of=None, max_estimate_age_hours=24):
    """Coverage source is an explicit caller declaration, never inferred from event counts.

    Estimates stay separate and block observed totals, even when fresh. Report
    scope is one intent/customer/period. Unallocated scope costs block assurance
    conservatively because their customer cannot be established.
    """
    errors = validate_records(records)
    if errors:
        raise ValueError('\n'.join(errors))
    if coverage_source is not None and not coverage_source.strip():
        raise ValueError('coverage source must be nonblank')
    if max_estimate_age_hours < 0:
        raise ValueError('maximum estimate age must be nonnegative')
    indexed = {r['id']: r for r in records}
    intent = indexed.get(intent_id)
    if not intent or intent['type'] != 'EconomicIntent':
        raise ValueError(f'{intent_id!r} is not an EconomicIntent in this store')
    period = _bounds(intent['period'])
    as_of = as_of or intent['period']['end']
    if not valid_timestamp(as_of):
        raise ValueError('as-of must be a valid UTC Z timestamp')
    clock = _time(as_of)
    if clock < period[1]:
        raise ValueError('as-of must be at or after the reporting period end')
    customer_id = indexed[intent['agreement_id']]['customer_id']
    scope = set(intent['cost_scope'])
    executions = {r['id']: r for r in indexed.values() if r['type'] == 'Execution'}

    def customer(execution):
        return indexed[execution['workload_id']]['customer_id'] if execution else None

    issues = []

    def issue(code, ids=()):
        entry = {'code': code, 'record_ids': sorted(ids)}
        if entry not in issues:
            issues.append(entry)

    if coverage_source is None:
        issue('COST_COVERAGE_UNDECLARED')
    selected_executions = {}
    for rid, execution in executions.items():
        if customer(execution) != customer_id:
            continue
        start, end = _time(execution['started_at']), _time(execution['ended_at'])
        if period[0] <= start < period[1] and end <= period[1]:
            selected_executions[rid] = execution
        elif start < period[1] and end > period[0]:
            issue('EXECUTION_CROSSES_PERIOD', [rid])

    superseded = {r['supersedes_id'] for r in indexed.values() if r['type'] == 'CostObservation' and 'supersedes_id' in r}
    observations = [r for r in indexed.values() if r['type'] == 'CostObservation' and r['id'] not in superseded]
    attributed, unallocated, incompatible = [], [], []
    for cost in observations:
        if cost['component'] not in scope or not _overlap(_bounds(cost['period']), period):
            continue
        owner = customer(executions.get(cost['execution_id']))
        if owner not in (None, customer_id):
            continue
        bounds = _bounds(cost['period'])
        if bounds[0] < period[0] or bounds[1] > period[1]:
            incompatible.append(cost)
            issue('COST_PERIOD_MISMATCH', [cost['id']])
            continue
        if owner is None:
            unallocated.append(cost)
            issue('UNALLOCATED_COST', [cost['id']])
        else:
            attributed.append(cost)
        if cost['status'] == 'unknown':
            issue('UNKNOWN_COST', [cost['id']])
        if _time(cost['observed_at']) > clock:
            issue('OBSERVATION_AFTER_AS_OF', [cost['id']])
        if cost['status'] == 'estimated':
            issue('ESTIMATED_COST', [cost['id']])
            if (clock - _time(cost['observed_at'])).total_seconds() > max_estimate_age_hours * 3600:
                issue('STALE_ESTIMATE', [cost['id']])

    for rid in selected_executions:
        components = {c['component'] for c in attributed if c['execution_id'] == rid}
        if scope - components:
            issue('MISSING_EXECUTION_COST', [rid])
    revenues = [r for r in indexed.values() if r['type'] == 'RevenueInput' and r['agreement_id'] == intent['agreement_id'] and _overlap(_bounds(r['period']), period)]
    revenue_issues = []
    if not revenues:
        revenue_issues.append('MISSING_REVENUE')
    elif len(revenues) != 1:
        revenue_issues.append('AMBIGUOUS_REVENUE')
    elif _bounds(revenues[0]['period']) != period:
        revenue_issues.append('REVENUE_PERIOD_MISMATCH')
    elif revenues[0]['completeness'] != 'complete':
        revenue_issues.append('INCOMPLETE_REVENUE')
    for code in revenue_issues:
        issue(code, [r['id'] for r in revenues])

    # Set precision from the inputs so large valid decimals do not round on sum.
    size = max([len(str(r.get('amount', '0'))) for r in observations + revenues] + [len(intent['service_cost_budget'])])
    with localcontext() as context:
        context.prec = max(40, size + len(str(len(indexed))) + 20)

        def subtotal(rows, status):
            return sum((Decimal(c['amount']) for c in rows if c['status'] == status), Decimal('0'))

        observed = subtotal(attributed, 'observed')
        estimated = subtotal(attributed, 'estimated')
        blockers = [x for x in issues if x['code'] not in revenue_issues]
        service_cost = observed if not blockers else None
        revenue = Decimal(revenues[0]['amount']) if not revenue_issues else None
        margin = revenue - service_cost if revenue is not None and service_cost is not None else None
        if revenue == 0:
            issue('ZERO_REVENUE', [revenues[0]['id']])
        successes = {(e['workload_id'], e['logical_task_id']) for e in selected_executions.values() if e['status'] == 'succeeded'}
        if not successes:
            issue('NO_SUCCESSFUL_TASKS', selected_executions)
        results = {
            'report_version': '0.2', 'intent_id': intent_id, 'customer_id': customer_id,
            'agreement_id': intent['agreement_id'], 'period': intent['period'],
            'currency': 'USD', 'cost_scope': sorted(scope), 'as_of': as_of,
            'coverage': {'declared_complete': coverage_source is not None, 'source': coverage_source, 'independently_verified': False},
            'max_estimate_age_hours': max_estimate_age_hours,
            'observed_cost_subtotal': _money(observed), 'estimated_cost_subtotal': _money(estimated),
            'unknown_cost_ids': sorted(c['id'] for c in attributed if c['status'] == 'unknown'),
            'service_cost': _money(service_cost), 'revenue': _money(revenue),
            'margin_amount': _money(margin),
            'margin_percent': _ratio(margin * 100, revenue) if margin is not None and revenue > 0 else None,
            'successful_tasks': len(successes),
            'cost_per_successful_task': _ratio(service_cost, Decimal(len(successes))) if service_cost is not None and successes else None,
            'budget_difference': _money(service_cost - Decimal(intent['service_cost_budget'])) if service_cost is not None else None,
            'unallocated': {'observed_subtotal': _money(subtotal(unallocated, 'observed')), 'estimated_subtotal': _money(subtotal(unallocated, 'estimated')), 'record_ids': sorted(c['id'] for c in unallocated), 'unknown_cost_ids': sorted(c['id'] for c in unallocated if c['status'] == 'unknown')},
            'incompatible_cost_ids': sorted(c['id'] for c in incompatible),
            'cost_evidence': sorted(attributed + unallocated + incompatible, key=lambda c: c['id']),
            'execution_ids': sorted(selected_executions), 'revenue_evidence': sorted(revenues, key=lambda r: r['id']),
            'issues': sorted(issues, key=lambda x: (x['code'], x['record_ids'])),
        }
    return results
