# ADR-0005: Sim/real parity via shared contracts

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** Software team

## Context
Hardware (sensors, mounting, the model truck) will not be ready early, and procurement may
slip. Yet the project must show progress, develop the warning logic and HMI, and be
demoable throughout — and ultimately deliver a "computer simulation model" anyway. We need
software progress to be **independent of hardware availability**.

## Decision
Make the **simulator and the real sensor rig interchangeable** by having both publish the
**identical** `bsw/sensor/#` and `bsw/vehicle` messages defined in
[`../04-message-protocol.md`](../04-message-protocol.md). The fusion engine and HMI consume
messages only and are **unaware of the source**. Switching from simulation to hardware
changes the *producer*, nothing downstream.

## Options Considered

### Option A: Shared message contract; sim == real producer (chosen)
**Pros:** Build/validate the full pipeline before hardware exists; the simulator *is* a
required deliverable; record/replay real logs for repeatable evaluation; one HMI/fusion
codebase for all deployments.
**Cons:** Requires contract discipline up front (freeze schemas early).

### Option B: Separate "demo mode" baked into the HMI
**Pros:** Quick hack for a single demo.
**Cons:** Fork between demo and real code paths → drift, double maintenance, untested real
path; the simulation wouldn't exercise the real fusion logic.

### Option C: Hardware-in-the-loop only (no pure-software sim)
**Pros:** Most realistic.
**Cons:** Blocks all software work on hardware; can't develop/demo early; no deterministic
regression tests.

## Trade-off Analysis
Option A is the project's biggest schedule de-risker for ~the cost of writing the schemas
carefully and early — which we must do regardless. It also turns the mandatory simulator
into a reusable test harness (scenario replay = regression suite) and produces the
evaluation evidence the proposal requires.

## Consequences
- **Easier:** parallel work; continuous demoability; deterministic tests; one codebase.
- **Harder:** schemas must be frozen at M1 and versioned; changes ripple to all producers/
  consumers (managed via `schema` version field and contract tests).
- **Revisit:** unlikely — this is foundational. Schema evolution handled by versioning,
  not by abandoning parity.

## Action Items
1. [ ] Freeze message schemas at milestone M1 ([`../09-roadmap.md`](../09-roadmap.md)).
2. [ ] Build the web simulator and the Python scenario runner to the same contract.
3. [ ] Add log record/replay tooling for evaluation (FR-10).
