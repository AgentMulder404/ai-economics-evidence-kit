# Participant challenge

This guide describes the planned v0.1 experience. Phase 1 validation is available now; use the quickstart in the repository README. The full replay, evaluator, and viewer experience remains planned for Days 2–4.

> Instrument an AI workflow, detect an economic problem, and propose a governed response supported by evidence.

## Pick a track

| Track | Build | Show in your demo |
| --- | --- | --- |
| Observability | A source adapter or attribution improvement | Trace a cost back to its source and customer; expose anything unallocated. |
| Ontology | A mapping or schema extension | Validate examples and explain the new concept without breaking existing relationships. |
| Governance | A versioned policy pack | Demonstrate a supported recommendation and a case where evidence forces a hold. |

Use synthetic data first. Real workloads are optional. Never submit credentials, customer records, or private prompt content.

## Submit

- A public repository or reviewable pull request with an explicit open-source license.
- Reproducible setup and demo instructions.
- Valid example events and the economic intention being evaluated.
- A drift scenario and an insufficient-evidence scenario.
- Evidence references, policy version, and an approval or rejection record.
- A short explanation of assumptions, cost scope, and remaining unknowns.

## Five-minute demo

1. Explain the workload and intended economics.
2. Replay the baseline and drift scenarios.
3. Trace the finding to its evidence.
4. Show the insufficient-evidence hold.
5. Record a human decision and explain who would execute it outside the kit.

## Judging

| Criterion | Weight |
| --- | --- |
| Attribution and provenance | 30% |
| Honest handling of uncertainty | 25% |
| Governance behavior and reproducibility | 25% |
| Usability and extension documentation | 20% |

Do not award savings based on non-equivalent workloads or degraded quality. A correctly held recommendation can be a better result than an unsupported claim of savings.
