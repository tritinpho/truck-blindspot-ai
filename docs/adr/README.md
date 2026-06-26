# Architecture Decision Records

Each ADR captures one significant decision: the context, the options, and the consequences.
Status values: Proposed · Accepted · Deprecated · Superseded.

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-0001](ADR-0001-edge-compute-platform.md) | Central compute platform | Accepted |
| [ADR-0002](ADR-0002-message-bus.md) | MQTT as the common message bus | Accepted |
| [ADR-0003](ADR-0003-hmi-stack.md) | Web stack for the in-cabin HMI | Accepted (framework refined by ADR-0009) |
| [ADR-0004](ADR-0004-sensor-modality.md) | Sensor modality strategy | Accepted |
| [ADR-0005](ADR-0005-sim-real-parity.md) | Sim/real parity via shared contracts | Accepted |
| [ADR-0006](ADR-0006-fail-loud-compute-liveness.md) | Fail-loud on compute death — watchdog + HMI liveness | Accepted |
| [ADR-0007](ADR-0007-sensor-firing-schedule.md) | Sensor firing schedule & realistic refresh rate | Accepted |
| [ADR-0008](ADR-0008-time-and-clock-domains.md) | Time, clock domains & cross-node age/latency | Accepted |
| [ADR-0009](ADR-0009-hmi-framework-vanilla-ts.md) | HMI UI framework — vanilla TS (refines ADR-0003) | Accepted |

These are *proposed/accepted for the design phase* and should be revisited if constraints
(budget, hardware availability, scope) change. ADR-0006 and ADR-0007 arose from the
architecture critique ([`../14-architecture-critique.md`](../14-architecture-critique.md)) and
were ratified 2026-06-26; their doc changes (NFR-01/02, §3.5, FR-15/NFR-12, TC-F4/F5,
`fire_group`, confirm-by-range) are applied. **ADR-0008** arose from the second round
([`../15-architecture-critique-round2.md`](../15-architecture-critique-round2.md)) and fixes
cross-node clock/age semantics.
