# AI Economics Evidence Kit

An open-source hackathon project for AI economic observability, a shared ontology, and evidence-based governance, inspired by NemulAI's AI Margin Assurance model.

**Status: Phases 1–2 implemented.** Versioned schemas, validation, transactional SQLite replay, customer cost attribution, and economic evidence reports are available. Policy evaluation, the viewer, and NemulAI integration remain planned.

> Make your AI app explain its economics—and know when there is not enough evidence to recommend a change.

## Run Phase 1

Requires Python 3.11 or later. From this repository:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[dev]'
evidence-kit validate examples/*.jsonl
python -m pytest -q
```

All four datasets should print `VALID`. For structured output, use `evidence-kit validate --json examples/healthy.jsonl`. Exit status is 0 when every file passes, 1 for invalid or unreadable data, and 2 for CLI usage errors. Errors identify the file, line, record, and offending field where available. The CLI reads local files and does not send data to a service.

After changing source code, reinstall with `python -m pip install '.[dev]'` before testing the installed package. See the [data dictionary](docs/DATA_DICTIONARY.md) and [fixture expectations](examples/README.md). Validation accepts explicit unknowns; it does not certify economic completeness.

## Replay and report

```sh
evidence-kit replay examples/healthy.jsonl --db healthy.sqlite
evidence-kit report --db healthy.sqlite --intent intent-1 \
  --coverage-source 'Synthetic healthy fixture: examples/README.md'
```

Use a separate database for each fixture. The coverage source is an explicit completeness declaration, not independent verification. Omit it to inspect known subtotals without asserting completeness. Unknown, estimated, unallocated, or incompatible costs prevent complete observed totals even with a declaration. See [Phase 2 usage and calculation rules](docs/PHASE_2.md).

## Start here

- [Four-day build plan](docs/FOUR_DAY_PLAN.md): daily deliverables, work packages, and acceptance gates.
- [Architecture and ontology](docs/ARCHITECTURE.md): proposed data model, economic calculations, and governance boundaries.
- [Participant guide](docs/PARTICIPANT_GUIDE.md): challenge, tracks, submissions, and judging.
- [Contributing](CONTRIBUTING.md): how to pick up a work package.

## The four concepts

| Concept | Meaning in the kit |
| --- | --- |
| Intention | An agreement's expected cost, target margin, quality floor, and approval authority. |
| Drift | Observed economics moving outside those intentions. |
| Judgment | An evidence-backed recommendation followed by a recorded human decision. |
| Instruments | Explicit attribution, completeness, freshness, and uncertainty checks. |

## Planned first release

Python, JSON Schema, SQLite, a local CLI, and a small Streamlit evidence viewer. A synthetic replay runs without credentials, GPU access, or paid APIs. One optional OpenTelemetry adapter connects real workloads to the canonical model.

The kit will recommend actions and record decisions. External systems remain responsible for execution. Proposed NemulAI import/export integration is deferred until its supported interface and licensing are verified; the local demo must work independently.

## Scope

Build one complete path: replay observations → validate and attribute costs → evaluate economic intent → show evidence gaps or drift → record a human decision.

Defer production connectors, automated enforcement, authentication, multi-currency conversion, graph databases, and a general-purpose policy language.

## License and relationship

MIT; see [LICENSE](LICENSE). This is an independent project inspired by [NemulAI's published framing](https://nemulai.com/docs), not a claim of official affiliation. No NemulAI source code is included.
