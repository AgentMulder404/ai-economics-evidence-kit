# AI Economics Evidence Kit

An open-source hackathon project for AI economic observability, a shared ontology, and evidence-based governance, inspired by NemulAI's AI Margin Assurance model.

**Status: planning scaffold.** No SDK, evaluator, dashboard, or NemulAI integration is implemented yet. The four-day plan below defines the first runnable release.

> Make your AI app explain its economics—and know when there is not enough evidence to recommend a change.

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
