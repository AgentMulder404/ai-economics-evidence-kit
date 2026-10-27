# Synthetic scenarios

Each JSONL file is self-contained. Run `evidence-kit validate examples/*.jsonl` from the repository root after installation.

Every scenario uses USD, an October 1–2, 2026 UTC period, $100 revenue, a $20 inference-cost budget, and a 70% margin target. These amounts are synthetic teaching inputs, not provider pricing. Fixture cost coverage is intentionally small and declared here for demonstration; validation alone does not establish completeness.

| File | Input cost arithmetic | Expected later-phase interpretation |
| --- | --- | --- |
| healthy.jsonl | One successful task costs $10; $90 margin, 90%. | Within budget and margin target; no intervention. |
| retry-drift.jsonl | Two failed attempts and one success on one logical task, $15 each: $45 total; $55 margin, 55%; $45 per successful task. | Cost exceeds budget by $25; investigate retries. |
| model-change.jsonl | Base-model task costs $10; subsequent premium-model task costs $35: $45 total; $55 margin, 55%; $22.50 per successful task. | Budget and margin drift coincide with a model change; this does not prove causality or equivalent quality. |
| missing-attribution.jsonl | $10 attributed, $5 unallocated, plus a separate unknown charge. Known overall subtotal $15; complete total and assured customer margin unavailable. | Hold recommendation; show the unknown charge and unallocated cost. |

The current CLI checks schema and relationships, not these arithmetic outcomes or policy decisions. Expected future outcomes are hand-calculated reference cases for Phases 2–3. Quality thresholds are declared but no quality measurements are supplied; intervention evaluation must not assume they were met.

Expected Phase 1 output:

```text
VALID examples/healthy.jsonl: 7 records
VALID examples/missing-attribution.jsonl: 9 records
VALID examples/model-change.jsonl: 9 records
VALID examples/retry-drift.jsonl: 11 records
```
