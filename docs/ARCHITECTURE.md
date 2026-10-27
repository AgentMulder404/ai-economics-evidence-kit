# Proposed architecture and ontology

Status: Phase 1 schemas/validation and Phase 2 replay, attribution, and calculations are implemented. Policy evaluation and the viewer remain planned. See [Phase 2 behavior](PHASE_2.md). See [the v0.1 data dictionary](DATA_DICTIONARY.md) for the exact implemented contract.

## Data flow

JSONL fixture or optional trace adapter → schema and relationship validation → SQLite evidence store → attribution and calculations → evidence gate → policy evaluation → local viewer and decision log.

Adapters translate source events; they must not silently invent customer identity or missing costs. Store original source identifiers, not prompt/completion bodies or credentials.

## Canonical entities

| Entity | Required meaning and relationships |
| --- | --- |
| Customer | Stable customer ID; optional display name. |
| Agreement | Customer ID, version, effective interval, revenue currency, service terms. |
| Workload | Customer ID when known, workload ID, task type. |
| Execution | Workload ID, logical task ID, attempt ID, start/end, status, model identifier when applicable. |
| CostObservation | Execution reference when known, cost component, decimal amount or explicit unknown, currency, observed/estimated/unknown status, source, observation time, effective period, method and pricing version for estimates. |
| EconomicIntent | Agreement version, effective period, service-cost budget, target margin, quality floor, permitted interventions, approval role. |
| DriftFinding | Intent reference, comparison period, observed result, threshold, source evidence IDs, rule version. |
| Recommendation | Finding IDs, proposed action, rationale, evidence snapshot, policy version, READY or HELD status, hold reasons. |
| Decision | Recommendation ID, approve/reject outcome, actor label, timestamp, rationale. |

Every record has a schema version and stable ID. Use UTC timestamps and half-open intervals [start, end). Preserve immutable source records; corrections supersede prior observations explicitly. Relationship validation is separate from JSON Schema validation.

Revenue is an explicit period input linked to the customer and agreement, with amount, currency, source, and completeness status. It is not inferred from token usage. Implement a revenue-input schema alongside the entity schemas.

## Calculation contract

- Use decimal arithmetic, not binary floating-point money. v0.1 supports USD only and rejects other currencies instead of silently converting them.
- Service cost includes all declared in-scope components and failed/retried executions. Prevent two observations of the same charge from being counted twice through a documented source ID/component key and correction mechanism.
- Margin amount = period revenue − period service cost. Margin percentage = margin amount / period revenue × 100, only for positive revenue and sufficiently complete inputs.
- Cost per successful task = all in-scope service cost / count of distinct successful logical tasks. With zero successes, return unavailable with a reason.
- Compare only compatible customer, period, currency, and cost scope. Label the scope: inference-only cost does not establish all-in business profitability.
- Budget drift = observed cost − intended budget. Model changes can correlate with drift; fixtures must not imply causal proof from correlation alone.
- Unknown values remain null with reason codes. Show known subtotals separately from complete totals.
- An event-count attribution ratio alone cannot prove monetary completeness. Use an independently supplied expected total or explicit completeness declaration; otherwise report coverage as unknown.

## Evidence and governance

Evaluate completeness before recommending interventions. Missing required revenue, material cost gaps, incompatible periods, and insufficient attribution produce HELD. Estimated costs may support a recommendation only if the versioned policy explicitly permits their method and freshness; label them visibly.

A READY recommendation is eligible for human review. A Decision records approval or rejection separately. Approval never means execution. New evidence creates a new evaluation linked to earlier results; it must not rewrite the old rationale.

The local append-only decision log supports demo traceability, not a tamper-proof or authenticated compliance system. Policy versions, input references, and calculation versions must be retained so a result can be reproduced.

## Proposed repository layout during implementation

```text
src/evidence_kit/schemas/ Versioned JSON Schemas bundled in the package
examples/                Synthetic JSONL and period inputs
src/evidence_kit/         CLI, storage, calculations, evidence gate, policies
src/evidence_kit/ui/      Local viewer
tests/                   Validation, calculations, replay, governance behavior
docs/                    Contracts, build plan, participant instructions
```

## Meaningful checks

Test duplicate replay, corrections without double counting, retries, zero successes, zero revenue, missing cost, unallocated observations, incompatible periods, and evidence holds. Use small fixtures with independently calculated expected results. Do not require external API access in CI.
