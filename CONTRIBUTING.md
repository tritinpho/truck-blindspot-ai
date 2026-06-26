# Contributing

Guide for the project team and collaborators working on the BSW software. The project is in
the **design phase**; this document covers how to contribute to the docs now and how the dev
workflow will look once code lands (per [`docs/03-architecture.md`](docs/03-architecture.md) §3.7).

## Ground rules

- The project is **contract-first**. The message contracts in [`schemas/`](schemas/) and
  [`docs/04-message-protocol.md`](docs/04-message-protocol.md) are the source of truth. If you
  change a contract, bump its `schema` version and update producers, consumers, and the docs
  together.
- Keep [`docs/12-traceability.md`](docs/12-traceability.md) honest — if you add a requirement,
  design, or test, add the trace.
- This is a **driver-assistance / advisory** system. Never add behavior that controls the
  vehicle. See [`LICENSE`](LICENSE) and [`docs/01-overview.md`](docs/01-overview.md) §1.7.

## Contributing to documentation (now)

1. Docs live in [`docs/`](docs/), numbered for reading order; ADRs in [`docs/adr/`](docs/adr/).
2. To propose a significant technical decision, add a new ADR (copy the format of an existing
   one) and link it from [`docs/adr/README.md`](docs/adr/README.md).
3. Use relative Markdown links between docs; embed diagrams as Mermaid so they render on the
   repo host and export cleanly for the report/infographic.
4. Bilingual where it helps stakeholders (EN engineering text, VI terms in the glossary,
   [`docs/01-overview.md`](docs/01-overview.md) §1.6).

## Planned development workflow (when code starts)

> Targets the repository structure in [`docs/03-architecture.md`](docs/03-architecture.md) §3.7.
> Not active yet — listed so the team aligns early.

### Prerequisites
- **Docker + Docker Compose** — run the whole stack (broker + fusion + HMI + simulator) on a laptop.
- **Python 3.11+** — fusion engine, vehicle adapter, tools.
- **Node.js LTS** — HMI and web simulator.
- **PlatformIO / Arduino** — ESP32 sensor-node firmware.

### Expected day-to-day (illustrative)
```bash
# bring up the dev stack (no hardware needed — sim/real parity)
docker compose -f deploy/docker-compose.yml up

# the simulator publishes synthetic bsw/sensor/# messages;
# the fusion engine publishes bsw/zone/#; the HMI renders them.
# open the HMI in a browser; open the simulator to place objects around the truck.
```

### Branch / commit / review
- Branch per change; do **not** commit to the default branch directly.
- Small, focused commits; reference the requirement or ADR ID where relevant
  (e.g. `FR-08`, `ADR-0005`).
- Open a PR; at least one teammate reviews. CI must pass (see below) before merge.

### Testing expectations (per [`docs/11-evaluation-plan.md`](docs/11-evaluation-plan.md))
- **L1 contract tests** — payloads validate against [`schemas/`](schemas/).
- **L2 logic tests** — fusion severity/debounce/context.
- **L3 scenario tests** — replay S1–S6 through the pipeline; these are regression tests.
- Add/extend tests with any behavior change; keep the scenario suite green.

### Coding conventions
- Lint + format per language (config to be added with the code): Python (ruff/black),
  TS/JS (eslint/prettier), firmware (clang-format).
- Externalize tunables to [`config/`](config/) — no magic numbers in code (FR-03/NFR-07).
- Structured logging (JSONL) for anything that should appear in the evaluation black-box.

## Reporting issues / ideas

Track work against the milestones in [`docs/09-roadmap.md`](docs/09-roadmap.md) and the
improvement list in [`docs/10-improvements.md`](docs/10-improvements.md). For a new technical
direction, prefer an ADR over a long discussion thread.
