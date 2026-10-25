# Schema v0.1 data contract

Phase 1 implements validation only. Passing validation means a dataset is structurally and relationally valid, not that its costs are complete, its margin is assured, or its proposed action is safe. Calculations and evidence gating are later phases.

## Format and versioning

Each UTF-8 JSONL file is a standalone dataset: one object per nonblank line, including all referenced records. File order is irrelevant. Multiple CLI arguments are validated independently, not merged. Empty files fail. Records use `schema_version: "0.1"`, a case-sensitive `type`, and a globally unique `id` within the dataset. IDs use letters, digits, underscores, dots, colons, and hyphens and begin with a letter or digit. Unexpected fields fail; place extensions in a future schema revision rather than silently discarding them.

The ten machine-readable schemas live in `src/evidence_kit/schemas/v0.1/` and ship inside the wheel. This is the frozen Phase 1 contract. Semantic or structural changes require a new schema version and migration notes. Package version 0.1.0 does not imply that the four-day product release is complete.

## Entities and fields

All fields are required unless marked optional below. Common fields are `id`, `type`, and `schema_version`.

| Record | Fields and meaning |
| --- | --- |
| Customer | Optional `name`; ID is the attribution identity. |
| Agreement | `customer_id`, `version`, `period`, `currency`, `service_terms`. Each version has its own immutable record ID. |
| Workload | `customer_id` (nullable for unknown attribution), `task_type`. |
| Execution | `workload_id`, `logical_task_id`, `attempt_id`, `started_at`, `ended_at`, `status` (`succeeded`/`failed`); optional `model`. One record represents one completed attempt. |
| CostObservation | `execution_id` (nullable), `component`, `amount`, `currency`, `status`, `source`, `observed_at`, `period`. Conditional `reason`, `estimate_method`, `pricing_version`; optional `supersedes_id`. |
| EconomicIntent | `agreement_id`, `agreement_version`, `period`, `currency`, `service_cost_budget`, `target_margin_percent` (0–100), `quality_floor` (0–1), `quality_metric`, `cost_scope`, `permitted_interventions`, `approval_role`. Lists are nonempty. |
| RevenueInput | `customer_id`, `agreement_id`, `period`, `amount`, `currency`, `source`, `completeness`; conditional `reason`. Revenue is not inferred from execution activity. |
| DriftFinding | `intent_id`, `period`, `observed_result` (nullable signed decimal string), `threshold` (signed decimal string), `metric`, `unit`, `evidence_ids`, `rule_version`, `reason_codes`. IDs and reasons are nonempty lists. |
| Recommendation | `finding_ids`, `proposed_action`, `rationale`, `evidence_ids`, `policy_version`, `status`, `hold_reasons`. READY requires no hold reasons; HELD requires at least one. |
| Decision | `recommendation_id`, `outcome` (`approve`/`reject`), `actor`, `decided_at`, `rationale`. Actor is a self-reported local label. A HELD recommendation cannot be approved. |

Governance records are input contracts only. The CLI does not generate recommendations, prove their rationale, authenticate actors, enforce append-only persistence, or execute decisions.

## Money, time, and scope

Money is a nonnegative decimal **string**, with 1–8 fractional digits: `"10.00"`, not `10.0`. Exponents, NaN, negatives, and unsupported currencies fail. USD is the only supported currency. Credits/refunds and currency conversion are out of scope for v0.1. Future arithmetic must use `Decimal` and documented rounding at presentation boundaries.

Timestamps use uppercase RFC 3339 UTC `Z`, with optional 1–6 fractional digits. A `period` has `start` and `end`, with start strictly before end; intervals are half-open `[start, end)`. Zero-duration executions are allowed, but their start must lie inside the cost observation period. Costs must cover their referenced execution. Intent/revenue periods must fit their agreement; finding periods must fit their intent.

Period containment does not establish comparability: Phase 2 must match exact calculation periods and cost scope before computing margins. Likewise, valid event counts do not establish monetary completeness. All four fixtures use inference-only scope, not all-in business profitability.

## Observed, estimated, and unknown

- `observed`: a known nonnegative amount reported by the declared source. This label is not independent verification.
- `estimated`: a known estimated amount, with required `estimate_method` and `pricing_version`.
- `unknown`: `amount: null` and a nonblank `reason`. Zero is prohibited as a substitute for unknown.
- Revenue completeness is `complete`, `partial`, or `unknown`. Complete/partial require a known amount; unknown requires null and a reason. Partial amounts are subtotals, not full-period assurance.
- `execution_id: null` or a workload's `customer_id: null` preserves unallocated evidence. A non-null reference must resolve to the correct entity type.

`source` contains nonblank `system` and stable `record_id`. Do not include credentials or private payloads. Provenance strings identify the declared source but do not attest authenticity.

## Identity, corrections, and relationships

Identical repeated records with the same ID validate successfully. Different contents with the same ID fail. The CLI reports input record count, including exact repeats; Phase 2 will implement storage idempotency.

An attempt is unique by `(workload_id, logical_task_id, attempt_id)`. Retries share a logical task ID and have different attempt IDs. Failed attempts still incur costs.

A charge is keyed by `(source.system, source.record_id, component)`. Two independent original observations of that key fail. A correction has a new record ID and `supersedes_id`, retains the source key, execution reference, and period, and has a strictly later `observed_at`. Correction chains must not branch. Phase 2 must use the latest correction once, preserving the originals for inspection.

Revenue's customer must match its agreement. Intent's agreement version must match its agreement record. Findings reference intents; recommendations reference findings; decisions reference recommendations. Evidence IDs must reference executions, cost observations, or revenue inputs. The CLI checks these links but does not yet prove that every item of governance evidence belongs to the same economic scope; that is part of Phase 3 evaluation.
