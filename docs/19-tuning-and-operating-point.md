# 19 — Tuning & the Operating Point (S6)

S6 picks the warning-logic **operating point** — the debounce/threshold values that balance
*sensitivity* (warn early and reliably) against *false alarms* (don't cry wolf, NFR-09) — and
**justifies it with data, not guesswork** (11 §11.6). The sweep is reproducible
([`tools/threshold_sweep.py`](../tools/threshold_sweep.py)) so it can be re-run when real **L4
bench** noise statistics arrive.

> **Scope caveat (read first).** The simulator derives detection from geometry and injects sensor
> *noise*, so this characterizes the **debounce response to sensor noise** — a defensible *starting*
> operating point. The **absolute false-positive rate** (real-world clutter, multipath, ground
> bounce) is an **L4 bench** number, not a sim number ([11 §11.2](11-evaluation-plan.md),
> [14 §P2 #6](14-architecture-critique.md)). S6 sets the debounce knobs; L4 confirms/refines them.

## 19.1 Method

`tools/threshold_sweep.py` sweeps the FR-09 anti-flicker levers (`confirm`, `release_margin_m`,
`release`, `immediate_danger_factor`) and scores each config on two axes:

- **Detection (sensitivity)** — clean RIGHT *approach* scenarios (deep → 0.5 m; boundary → 0.9 m),
  no context boost, real group-fire rate. Metric: danger-path **latency** (time from crossing
  `danger_m` to confirmed DANGER) and did-it-reach-DANGER.
- **Nuisance (false-alarm proxy)** — a noisy object hovering *just outside* `danger_m` (1.06 m and
  1.15 m vs `danger_m` 1.0 m, σ = 0.12–0.15 m, continuous sampling). Correct behaviour is to **hold
  CAUTION**. Metrics, averaged over many noise seeds: spurious **DANGER episodes/run**, **dwell %**
  (fraction of the run wrongly in DANGER), and **flicker**.

**Real-path latency adjustment (important).** The sim measures only the *fusion debounce*
contribution. The end-to-end NFR-01 budget also pays the physical path the sim omits — sensor
sample+publish (~30) + broker×2 (~10) + HMI render+audio (~30) ≈ **70 ms** ([03 §3.5](03-architecture.md)).
So a config is judged against the requirement using **estimated real latency = sim debounce + 70 ms**;
i.e. we must leave ~70 ms of headroom in-sim. This is what correctly rules out `confirm=3`.

## 19.2 Results

`confirm × release_margin_m` (release=4, immediate_danger_factor=0.6; nuisance over 12 seeds):

| confirm | margin | sim lat (deep/bnd) | est-real | within budget? | nuisance DANGER/run | dwell % | flicker |
|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | 0.10 | 0/0 | 70/70 | yes | 1.21 | 76.5 | 0.92 |
| 1 | 0.20 | 0/0 | 70/70 | yes | 0.75 | 82.5 | 0.12 |
| 1 | 0.30 | 0/0 | 70/70 | yes | 0.67 | 86.0 | 0.00 |
| **2** | **0.20** | **100/100** | **170/170** | **yes** | **0.46** | **58.2** | **0.00** ← **chosen (current default)** |
| 2 | 0.10 | 100/100 | 170/170 | yes | 0.58 | 48.8 | 0.29 |
| 2 | 0.30 | 100/100 | 170/170 | yes | 0.46 | 62.8 | 0.00 |
| 3 | 0.10–0.30 | 200/200 | 270/270 | **no** (>200 ms danger-path) | 0.25 | 30.8–44.8 | ≤0.08 |

`release` sweep (confirm=2, margin=0.2): dwell rises 47%→61% as release 2→6 with flicker reaching 0
by release=3; `release=4` keeps flicker 0 with sticky-clear bias toward safety.
`immediate_danger_factor` 0.4–0.7: no effect on these scenarios (it only changes the *deep* 1-tick
path), so 0.6 is retained.

## 19.3 Decision — the operating point

**Keep the current defaults**, now backed by data:

| Tunable | Value | Why (from the sweep) |
|---|---|---|
| `confirm` | **2** | `confirm=3` is the lowest-nuisance row but its est-real latency (270 ms) **breaks the 200 ms danger-path budget**; `confirm=1` meets latency but is far too trigger-happy (≈1 false DANGER/run, flicker ≤0.92). `confirm=2` is the knee: 100 ms sim / ~170 ms est-real, comfortably within budget. |
| `release_margin_m` | **0.20** | The only `confirm=2` setting with **zero flicker** *and* the fewest false-DANGER episodes (0.46). `0.10` chatters (flicker 0.29); `0.30` is stickier (dwell 62.8% vs 58.2%). FR-09 names *no flicker* as the target, so 0.20 wins. |
| `release` | **4** | Slower-to-clear than to-warn (safety bias); flicker already 0, dwell penalty small. |
| `immediate_danger_factor` | **0.6** | Preserves the ADR-0007 deep-danger 1-tick fast path; no effect on the boundary trade-off. |
| per-zone `danger_m`/`caution_m`, `risk_weight` | unchanged | Geometry/zone-design choices; **live-tunable at runtime via `bsw/cmd/set_threshold`** (S5) without a rebuild, so they can be adjusted on the bench during L4 without re-deploying. |

No config change was required — the sweep **validates** the designed defaults sit at the
sensitivity/false-alarm knee under the real-path latency constraint. The 91-test suite is therefore
unchanged.

## 19.4 Honest read & next steps

- The nuisance **dwell is high (~58%)** on the deliberately harsh scenario (object 6 cm outside
  `danger_m` with 12 cm noise): once noise trips DANGER, the safety-biased hysteresis latches it.
  This is inherent to a warn-early/clear-slow policy and is the right bias for a *danger* alert; the
  question of whether real ultrasonic noise is this severe is an **L4** measurement.
- **Re-run at L4:** feed measured bench noise σ and a real nuisance corpus into the same sweep
  (`python tools/threshold_sweep.py`) to confirm or nudge the point; log the sweep so the chosen
  value is auditable (11 §11.6). Per-zone thresholds can be swept live over `bsw/cmd`.
- **Cosmetic polish:** the day/night/auto HMI theme is **done** (Settings → Theme; high-contrast
  daylight + dark night, persisted, auto-by-time-of-day; safety semantics unchanged across themes).
  Demo-build packaging remains a small deferred S6 tail (cut-first, §16.7).

## 19.5 Reproduce

```bash
python tools/threshold_sweep.py                 # the confirm × margin grid + recommendation
python tools/threshold_sweep.py --seeds 30      # steadier nuisance means
python tools/threshold_sweep.py --release --idf # also sweep release / immediate_danger_factor
```
