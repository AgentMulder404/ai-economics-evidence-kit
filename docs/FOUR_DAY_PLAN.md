# Four phases in four days

## Delivery assumptions

Four focused build days for a small team of 2–4 contributors. One experienced developer can follow the same sequence by cutting the optional trace adapter and visual polish first. Each day ends with an executable acceptance gate; documentation alone does not complete a phase.

Target: a local, openly licensed starter participants can run in 15 minutes and extend during a hackathon. Python is the only application language. Pin dependency versions during implementation. Use synthetic data by default.

## Day 1 / Phase 1 — Define economic meaning

Implemented and merged in Phase 1: package, CLI, ten schemas, four fixtures, data dictionary, and validation tests. See the README for the acceptance commands.

**Outcome:** validated examples with a shared meaning for cost, intent, evidence, and decisions.

Work packages:

- D1-01: Create Python package, CLI entry point, dependency metadata, and basic CI. Add a schema-validation command.
- D1-02: Implement versioned JSON Schemas for Customer, Agreement, Workload, Execution, CostObservation, EconomicIntent, DriftFinding, Recommendation, and Decision. Use the architecture document as the starting contract.
- D1-03: Create four deterministic fixtures: healthy economics, retry-driven drift, a model-change scenario, and missing attribution. Include matching revenue and agreement periods.
- D1-04: Document units, identifiers, provenance, idempotency, period boundaries, and how observed/estimated/unknown values differ.

**Acceptance gate:** all four fixtures validate; malformed amounts, unsupported currencies, missing identifiers, and invalid relationships produce actionable errors. An unknown cost remains unknown rather than becoming zero. Document the command and expected output.

**Deliverables:** schemas, fixtures, validation CLI, data dictionary, CI.

**Dependency:** none. Freeze schema v0.1 at the end of the day; record later changes explicitly.

## Day 2 / Phase 2 — Observe and attribute

Implemented on the Phase 2 branch: transactional replay, customer attribution, decimal reporting, and local evidence checks. See [Phase 2 usage](PHASE_2.md). The optional live OpenTelemetry adapter is deferred.

**Outcome:** replay execution records into a local evidence store and explain each attributed cost.

Work packages:

- D2-01: Add SQLite persistence and JSONL ingestion with transactional writes and duplicate-event handling.
- D2-02: Implement execution → workload → customer attribution. Preserve unattributed observations in a visible unallocated bucket.
- D2-03: Compute period totals, cost per successful task, and customer margin only when inputs meet the declared evidence requirements. Keep actual, estimated, and missing amounts distinct.
- D2-04: Add evidence checks for missing customer IDs, stale estimates, incompatible periods, and incomplete cost coverage. Optionally implement one OpenTelemetry mapping after replay works.

**Acceptance gate:** replaying identical input twice leaves totals unchanged. Fixture totals match independently calculated expected amounts. Failed attempts and retries contribute cost; only successful logical tasks enter the success denominator. Unattributed costs are visible and prevent unsupported assurance claims.

**Deliverables:** ingest/replay CLI, database, aggregation functions, evidence report, focused calculation tests.

**Dependency:** Day 1 schemas and fixtures.

## Day 3 / Phase 3 — Govern recommendations

**Outcome:** deterministic findings and recommendations with explicit evidence and human decisions.

Work packages:

- D3-01: Implement three versioned rules: service cost exceeds budget; customer margin falls below target; insufficient evidence holds a recommendation.
- D3-02: Define a configurable evidence gate: required inputs, permitted estimate types, freshness, and attribution coverage. Record the applied settings with the result.
- D3-03: Attach source observation IDs, agreement/intent version, calculation period, policy version, and reason codes to every finding.
- D3-04: Add append-only approval/rejection records with actor, timestamp, and rationale. Distinguish a recorded approval from an executed action. Local actor names are self-reported, not authenticated identities.

**Acceptance gate:** healthy data produces no intervention; retry drift produces a supported recommendation; missing material cost or revenue produces HELD with a specific reason; a human can approve or reject a recommendation without modifying its evidence. Identical inputs and policy versions produce identical substantive results.

**Deliverables:** evaluator, three policy examples, evidence gate, decision log, behavioral tests.

**Dependency:** Day 2 attributed observations and evidence checks.

## Day 4 / Phase 4 — Make it usable at the hackathon

**Outcome:** a clean-machine demo and an extension path participants can use immediately.

Work packages:

- D4-01: Build a minimal Streamlit viewer: intention, cost/revenue/margin, drift findings, evidence gaps, and decision history. Display HELD prominently and never as a healthy result.
- D4-02: Add a single documented demo command that initializes the store, replays fixtures, evaluates rules, and launches the viewer. Include reset instructions scoped to demo data.
- D4-03: Finish participant quickstart, adapter and policy extension examples, judging rubric, and submission checklist. Label starter issues by observability, ontology, and governance.
- D4-04: Rehearse on a clean environment, validate license/dependency notices, run the acceptance suite, and tag v0.1.0 only when gates pass.

**Acceptance gate:** a new participant reaches the four fixture outcomes in 15 minutes without credentials or paid services. They can add one custom rule or map one new event format using the documented example. Verify both the CLI and viewer against the same stored results.

**Deliverables:** viewer, demo command, quickstart, extension examples, release notes, v0.1.0.

**Dependency:** Days 1–3 working end to end.

## Daily rhythm

- First 30 minutes: replay yesterday's gate, agree the day's boundary, assign work packages.
- Main build block: implement the smallest end-to-end slice before optional improvements.
- Final hour: run the gate, update docs, demonstrate the outcome, record remaining risks.

Suggested ownership with three people: one owns schemas/fixtures and docs, one owns ingestion/calculations, and one owns policies/viewer. Owners pair on handoffs; dependent tasks start only when their contracts are ready.

## Scope cuts and release bar

If behind: cut the live trace adapter first, then charts, then packaging conveniences. Retain schemas, replay, correct arithmetic, evidence holds, provenance, and human decisions. A CLI-only demo is preferable to an incomplete assurance workflow.

Do not call the release complete if unknown costs appear as zero, duplicate ingestion changes totals, missing evidence produces confident recommendations, or approval is presented as execution.

## After the four days

Gather participant feedback before building production connectors. Verify NemulAI's supported data contracts before adding integration. Authentication, tamper-resistant storage, production operation, and automated execution require separate designs and are outside v0.1.
