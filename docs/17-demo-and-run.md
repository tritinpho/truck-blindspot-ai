# 17 — Demo & Run Book (M3)

How to run the **full pipeline end-to-end** and reproduce the M3 evidence. M3 (the linchpin
milestone, [`09-roadmap.md`](09-roadmap.md)) means: scenarios **S1–S6 + the fault cases run
end-to-end green in CI/sim**, the pipeline is **demoable** (broker → fusion → HMI driven by the
scripted sim, including the boot *warming-up* screen and TC-F4 *kill → SIGNAL LOST*), and **logs
replay reproducibly**. Tuning the defaults to a credible operating point is **S6**, not M3.

Everything here needs **no hardware** (sim/real parity, [ADR-0005](adr/ADR-0005-sim-real-parity.md)).

---

## 0. Prerequisites

- **Docker** (for the one-command broker + fusion bring-up), or a local Mosquitto.
- **Python 3.11+** (`pip install -r tests/requirements.txt` for the suite; the fusion engine also
  needs `pip install -r services/fusion-engine/requirements.txt` to run outside Docker).
- **Node 22+** (only to run the HMI dev server / `npm test`; the served HMI image needs nothing local).

## 1. Tests first — no broker needed

The whole logic + wiring story is provable with **zero infrastructure** (this is what CI runs on
every push):

```bash
pip install -r tests/requirements.txt
pytest -q tests/ services/fusion-engine/tests
```

What runs (all deterministic, no broker, no wall-clock):

| Level | Files | Proves |
|-------|-------|--------|
| **L1** contract | `tests/test_contracts.py` | every message + both configs validate vs `schemas/` |
| **L2** fusion logic | `services/fusion-engine/tests/` | severity, debounce, hysteresis, staleness, context, **bsw/cmd** |
| **L3** scenarios | `tests/test_scenarios.py` | S1–S6 + F1/F2/F3/F5 through the real engine in-process |
| **L3** integration shim | `tests/test_integration_shim.py` | the **live path** (publisher → bus → fusion routing → retained `bsw/zone` → subscriber) matches the in-process L3 outcomes |
| tool cores | `tests/test_tools.py` | `log_replay` + `latency_observer` metric maths |

The **integration shim** is the key S5 addition: it runs the *real* `FusionService` and the *real*
scenario wire stream over an in-process loopback bus, so it asserts the wired pipeline produces the
same result as the logic tests — without needing Docker. The broker-backed equivalent over real
TCP is `tests/test_integration_broker.py` (it **skips** unless a broker + fusion are up, §6).

## 2. One-command bring-up (broker + fusion)

> **Quickest path — the whole demo in one command.** `python tools/demo.py` brings up the stack
> (broker + fusion + HMI at :8080, the `hmi` profile), waits for the broker, opens the HMI in your
> browser, and drives the narrated S1/S2+fault/S4/S6 timeline (`tools/sim_demo.py`). Ctrl-C stops the
> drive but leaves the stack up so you can keep poking the HMI; `python tools/demo.py --down` removes
> it. `--no-up` if the stack is already running, `--no-browser` for a headless box. This collapses
> §2–§4 below — which remain the manual, step-by-step path when you want to drive the pieces yourself.

```bash
docker compose -f deploy/docker-compose.yml up -d        # broker (:1883 / :9001) + fusion engine
docker compose -f deploy/docker-compose.yml logs -f fusion   # watch it connect + tick
```

`fusion` connects to the broker by service name and publishes retained `bsw/zone/#` at 10 Hz plus a
1 Hz `bsw/health/fusion` heartbeat (with an MQTT Last-Will). It mounts `config/` (read-only — live
edits are picked up by `reload_config`) and `logs/` (so `tools/log_replay.py` on the host sees
`events.jsonl`). If fusion starts before the broker is ready it simply restarts until it connects.

> No Docker? Run the broker any way you like and start fusion directly:
> `cd services/fusion-engine && pip install -r requirements.txt && python -m fusion`

## 3. Drive a scenario (the scripted sim)

With the stack up, push a scenario onto the bus from the host — same wire messages a real rig emits:

```bash
# geometry-driven, one scenario at a time (S1..S6, F1..):
python tools/scenario_runner.py S2 --live      # right-turn squeeze → RIGHT DANGER, banner=RIGHT
python tools/scenario_runner.py S4 --live      # reversing → REAR DANGER

# or the narrated multi-zone timeline that exercises the whole HMI:
python tools/sim_demo.py                        # zone tints, banner, audio, standby, a dropout→UNKNOWN
```

`scenario_runner.py` with **no** `--live` prints the deterministic outcomes (no broker) — handy to
see the expected result before driving it live:

```bash
python tools/scenario_runner.py                 # every scenario's finals / worst-zone / audio
python tools/scenario_runner.py S2 -v           # tick-by-tick timeline for one scenario
```

## 4. Open the HMI

Either serve the built HMI from the stack:

```bash
docker compose -f deploy/docker-compose.yml --profile hmi up -d   # → http://localhost:8080
```

…or run the Vite dev server (hot reload, the usual dev loop):

```bash
cd apps/hmi && npm install && npm run dev        # → http://localhost:5173
```

The HMI connects to `ws://localhost:9001` and renders the top-view: zone tints by severity, object
icons, the primary-alert banner (worst `risk_weight × severity`), escalating audio, and the
liveness pip. Click once to unlock audio (browser autoplay policy).

## 5. The fail-loud demos (keep these ruthlessly — the safety story)

These are part of the M3 exit, not extras:

- **Warming-up (boot, NFR-12).** Start the **HMI first**, before fusion. It shows *"warming up —
  not yet monitoring"* (never a misleading "all clear") until the first `bsw/zone` arrives.
- **TC-F4 — compute freeze → SIGNAL LOST (FR-15, [ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md)).**
  With the pipeline live and the HMI monitoring, kill fusion:
  ```bash
  docker compose -f deploy/docker-compose.yml kill fusion     # or Ctrl-C a `python -m fusion`
  ```
  Within the freshness window (~1 s) the whole map degrades to **UNKNOWN**, the banner shows
  **SIGNAL LOST**, and the "alive" pip stops animating. The MQTT Last-Will makes an *ungraceful*
  kill trip it immediately. Restart fusion → it recovers to MONITORING automatically.
- **TC-F1 — sensor unplugged → UNKNOWN.** `sim_demo.py` includes a phase that stops publishing the
  RIGHT sensor; that zone ages to **UNKNOWN** (hatched) + a one-shot fault chime — never a fake SAFE.

## 6. Broker-backed integration test (optional, real TCP)

The same assertions as the shim, but over a real broker + fusion:

```bash
docker compose -f deploy/docker-compose.yml up -d     # broker + fusion
pytest -q tests/test_integration_broker.py            # publishes S2/S4 live, asserts bsw/zone
```

It self-skips with a clear message if no broker (or no fusion heartbeat) is found, so it never
breaks a no-Docker run. Point it elsewhere with `BSW_BROKER_HOST` / `BSW_BROKER_PORT`.

## 7. Reproducible logs (11 §11.6)

A live run writes zone-severity transitions to `logs/events.jsonl`. Recompute the report metrics:

```bash
python tools/log_replay.py            # default logs/events.jsonl → transitions / to-DANGER / flicker
```

Replaying the **same** log always yields the **same** numbers (the metric core is pure). The
determinism is enforced by `tests/test_reproducibility.py`: it drives a scenario through fusion
twice and asserts the two transition logs — and therefore the replayed metrics — are byte-identical.

## 8. Latency (indicative only — headline is L4 bench)

```bash
python tools/latency_observer.py &                    # tap bsw/sensor/# (stimulus) + bsw/zone/# (effect)
python tools/scenario_runner.py S2 --live             # drive; Ctrl-C the tap for the summary
```

This measures the danger-path end-to-end on a **single observer clock** (you cannot subtract an
ESP32 `ts` from a Pi `ts`, [ADR-0008](adr/ADR-0008-time-and-clock-domains.md)). On the sim path the
numbers are **indicative** — the headline detection/latency figures must come from **L4 bench**,
because the simulator derives detection from zone geometry ([11 §11.2](11-evaluation-plan.md),
[14 §P2 #6](14-architecture-critique.md)). An indicative danger-path estimate from the deterministic
timeline is printed by `python tools/scenario_runner.py --latency`.

## 9. Tear down

```bash
docker compose -f deploy/docker-compose.yml --profile hmi down
```
