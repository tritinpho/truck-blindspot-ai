# services/vehicle-adapter — vehicle signals → `bsw/vehicle` (optional)

Reads turn-signal / gear / speed from GPIO wiring or OBD-II/ELM327 and publishes `bsw.vehicle`
context for the anti-alert-fatigue logic (FR-08, [05 §5.4](../../docs/05-warning-logic.md)).
`gear` is the single source of truth for drivetrain state — "reversing" is `gear == "reverse"`
(R2-2, no separate flag).

**Optional / deferred.** Where vehicle signals are unavailable the system degrades to
"monitor all zones"; on the bench the simulator supplies these signals. **Not on the M3 path.**
