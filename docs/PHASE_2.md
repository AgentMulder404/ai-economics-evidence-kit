# Phase 2: local economic evidence

Phase 2 adds SQLite replay and deterministic JSON reports. Schema v0.1 is unchanged. Policy recommendations, approval workflows, the viewer, and live telemetry integrations remain later work.

## Run a scenario

From the repository root after `python -m pip install '.[dev]'`:

```sh
evidence-kit replay examples/healthy.jsonl --db healthy.sqlite
evidence-kit replay examples/healthy.jsonl --db healthy.sqlite
evidence-kit report --db healthy.sqlite --intent intent-1 \
  --coverage-source 'Synthetic healthy fixture: examples/README.md'
```

The first replay inserts 7 records. The second inserts 0 and reports 7 duplicates. The report shows service cost `10.00`, revenue `100.00`, margin amount `90.00`, and margin percentage `90.00000000`.

Each fixture reuses synthetic IDs, so use a **separate database per scenario**. Mixing fixtures intentionally fails with conflicting-record errors. Multiple input files may be supplied to one replay when they belong to the same dataset; references may resolve against the entire batch or existing store.

```sh
evidence-kit replay examples/missing-attribution.jsonl --db missing.sqlite
evidence-kit report --db missing.sqlite --intent intent-1
```

This shows $10 attributed observed cost, $5 unallocated observed cost, and an unknown charge. Complete service cost and margin remain null. Even a coverage declaration cannot override these evidence gaps.

## What the coverage declaration means

`--coverage-source` is an explicit user assertion that all costs for the selected customer, period, and scope are represented. Supply a meaningful source such as a reconciled provider export. The report records the declaration and marks it **not independently verified**. Do not use it simply to make a report populate totals. Without it, only known subtotals are shown. Event counts alone never establish monetary completeness.

Revenue additionally needs one complete input for exactly the selected agreement and reporting period. Partial, unknown, missing, overlapping mismatched, or multiple revenue inputs block margin. Multiple invoices must be consolidated upstream into one sourced period input for this version; they are not automatically summed.

## Attribution and arithmetic

- The selected EconomicIntent supplies agreement, customer, period, currency, and cost scope.
- Active CostObservations follow execution → workload → customer. A null execution or customer creates unallocated cost. Other customers' attributed costs are excluded.
- In-scope unallocated costs conservatively block a complete customer total because their owner is unknown.
- All failed and successful attempts contribute cost. Successful logical tasks are distinct `(workload_id, logical_task_id)` pairs, not attempt counts. Period-level task cost includes all selected costs, including failures.
- Each selected execution needs a charge observation for every declared scope component; use an explicit observed zero for genuinely free components. Absence is not zero.
- Costs wholly contained in the intent period can be summed. Charges crossing the period boundary remain in incompatible evidence and are never prorated. Crossing executions also block complete totals. Wholly outside-period charges are excluded.
- Service cost and budget difference use observed costs only and require no cost-evidence blockers. Estimated costs are reported separately and always block observed complete totals in Phase 2.
- Margin amount is revenue minus complete service cost. Percentage requires positive revenue. Zero revenue still permits a negative margin amount, but yields null percentage with `ZERO_REVENUE`.
- Cost per successful task requires complete service cost and at least one successful task. Zero successes yields null with `NO_SUCCESSFUL_TASKS`.
- Decimal arithmetic preserves source precision for sums/differences. Division outputs eight fractional digits using round-half-even. Reports are inference-scope economics when the intent specifies inference, not all-in company profitability.

## Freshness and reproducibility

`--as-of` is a freshness reference, defaulting to the intent's period end. It must be a UTC Z timestamp at or after the reporting period end. Estimates older than `--max-estimate-age-hours` (default 24) are flagged stale. This measures observation age, not the validity of a provider's pricing version. Observations after the reference time also block complete totals.

Reports use the latest stored correction and are **not historical snapshots**. For a later correction, advance `--as-of` to cover its observation time; the report does not reconstruct what was known at an earlier date. Reports include active cost records and source metadata, revenue inputs, execution IDs, coverage settings, scope, and specific issue codes. Save JSON output with shell redirection if you need a report artifact. Reporting does not alter the database or create one when the path is missing.

## Transaction and correction behavior

Replay takes a SQLite write lock before reading and validating the combined store and batch. All inserts commit together or roll back. Original records are immutable: identical IDs/payloads are no-ops; changed payloads under an existing ID fail. Duplicate source-charge identities require a valid linear correction chain. Reports count only the active terminal observation; originals remain in the store and replaying them cannot resurrect their cost.

The local database is not an authenticated or tamper-resistant audit log. Reporting revalidates stored data, but cannot prove source authenticity. Revenue correction semantics, production-scale ingestion, migrations, and authenticated concurrent services are outside this phase.

## Exit behavior

`replay` and `report` return JSON on stdout; malformed input, invalid relationships, storage failures, and invalid report settings return JSON errors on stderr with exit code 1. A successfully generated report returns 0 even if it contains evidence gaps. Consumers must inspect `issues` and nullable totals; exit success is not economic assurance.

## Acceptance cases

| Scenario | Service cost | Margin | Successful tasks | Cost per successful task |
| --- | --- | --- | --- | --- |
| Healthy, coverage declared | $10 | $90 / 90% | 1 | $10 |
| Retry drift, coverage declared | $45 | $55 / 55% | 1 | $45 |
| Model change, coverage declared | $45 | $55 / 55% | 2 | $22.50 |
| Missing attribution | Unavailable | Unavailable | 1 | Unavailable |

Run `python -m pytest -q` for fixture arithmetic, repeat ingestion, rollback, corrections, customer attribution, revenue gaps, period boundaries, estimates, decimal precision, and CLI checks.
