# ADR-0008: Time, clock domains & cross-node age/latency

**Status:** Accepted (ratified 2026-06-26)
**Date:** 2026-06-26
**Deciders:** PI (Nguyễn Cảnh Tuấn), software lead (ThS. Phó Trí Tín), hardware liaison

## Context
Every message carries `ts` + `ts_kind` (`epoch_ms | monotonic_ms`). Three nodes keep time
very differently:

- **ESP32 sensor nodes** have **no RTC** → they publish `monotonic_ms` (milliseconds since
  *their own* boot). Node A's boot-relative clock has no fixed relation to node B's or to the
  Pi's wall clock.
- **The Raspberry Pi also has no RTC.** Its `epoch_ms` is wrong until NTP syncs, and a bench
  rig may be offline — so even the Pi's "epoch" is unreliable during the **boot window**, the
  exact moment scenario S1 / NFR-12 cares about.
- **The HMI** (browser) has a clock, but it is a *consumer*.

[03 §3.8](../03-architecture.md) said "all messages carry a **monotonic** `ts` … fusion uses
**message age** for staleness." That conflates two clocks: computing age as
`consumer_now − message.ts` subtracts a **foreign node's** clock from the consumer's and is
meaningless across domains. It happens to work in the single-process simulator (one clock for
everything) and **breaks on the bench** — the same "sim hides hardware reality" failure class
called out in [14 §P2 #6/#7](../14-architecture-critique.md). The NFR-01 **latency
measurement** has the same flaw: you cannot subtract an ESP32 publish-`ts` from an HMI
render-`ts`.

## Decision
1. **Staleness & liveness are measured from local arrival time — never from a foreign `ts`.**
   Every consumer tracks, per source, the **local receipt time** of the last message on its
   *own* monotonic clock, and ages it as `local_now − local_receipt`. `stale_after_ms`,
   `stale_confirm` ([05 §5.3](../05-warning-logic.md)), and the HMI freshness window
   ([ADR-0006](ADR-0006-fail-loud-compute-liveness.md)) are all evaluated this way.
2. **`ts` is for ordering and display only.** Producers still stamp `ts`/`ts_kind`; it is used
   for ordering and relative timing *within one clock domain* and for human-readable logs —
   not for cross-node age.
3. **Latency (NFR-01) is measured at a single observer.** A tap subscribes to both the
   stimulus (`bsw/sensor`/sim publish) and the effect (`bsw/zone`/HMI render) and timestamps
   both with **its own** clock → a single-clock delta. This is always valid regardless of node
   clocks. The simulator measures latency trivially (one process).
4. **The logger stamps each event with its own receipt time** (authoritative for analysis),
   alongside the producer `ts`.

## Options Considered

### Option A: Local-arrival-time for age + single-observer latency (chosen)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low (consumers already see messages; track receipt time per source) |
| Cost | Zero |
| Correctness | Valid on heterogeneous, unsynced, RTC-less, pre-NTP clocks |
| Fit | Reuses existing fields; underpins ADR-0006 liveness on a sound basis |

**Pros:** Always correct; no hardware; sim and bench behave identically; needs only a tiny
latency-observer tool (already implied by `tools/` replay).
**Cons:** End-to-end latency needs an observer tap rather than naïve `ts` subtraction.

### Option B: SNTP-sync every node to a common clock, then trust `ts` subtraction
**Pros:** `ts` becomes globally comparable.
**Cons:** Needs network + sync discipline on every MCU; **fails offline and at boot** — the
exact S1/NFR-12 window; fragile. Kept as an *optional bench aid* for comparable `ts`, not as
the contract.

### Option C: Broker-stamped receive time (MQTT 5 property / republish)
**Pros:** Collapses to one clock (the Pi/broker).
**Cons:** Mosquitto does not stamp app-level receive time by default; adds a hop and
non-standard handling. Rejected as the primary mechanism.

## Trade-off Analysis
Clock skew across RTC-less nodes is a hard physical fact, not a tuning knob. Option A makes
correctness independent of it for ~zero cost and rests the already-ratified liveness logic
(ADR-0006) on a sound footing. Option B is a convenience that collapses precisely when it is
needed most (offline, at boot), so it is demoted to an optional aid. The contract therefore
treats `ts` as advisory and makes **local receipt time** authoritative for age.

## Consequences
- **Easier:** staleness/liveness correct on the bench, not just in sim; "kill-the-compute →
  UNKNOWN" (ADR-0006) is well-founded; sim/bench parity holds for timing too.
- **Harder:** a small `tools/` latency observer is needed; fusion/HMI must track per-source
  receipt time; [03 §3.8](../03-architecture.md) and [04 §4.1](../04-message-protocol.md)
  wording corrected (done with this ADR).
- **Revisit when:** the vehicle pilot moves the sensor hop to **CAN** ([10 #14](../10-improvements.md)) —
  CAN brings its own timestamping; revisit then.

## Action Items
1. [ ] Fusion: per-sensor staleness from **local receipt time**; emit locally-stamped event logs.
2. [ ] HMI: freshness clock from local receipt of zone/heartbeat (already [ADR-0006](ADR-0006-fail-loud-compute-liveness.md)), explicitly **not** from `ts`.
3. [ ] `tools/`: a latency observer that timestamps stimulus + effect with one clock; extend the NFR-01 test in [11](../11-evaluation-plan.md).
4. [ ] Optional: SNTP client on the ESP32 for bench-grade comparable `ts` (aid only, never relied on for safety).
5. [x] Docs: corrected [03 §3.8](../03-architecture.md) and added the clocks-&-age rule to [04 §4.1](../04-message-protocol.md).
