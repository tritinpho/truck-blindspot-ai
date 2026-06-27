# 18 — M3 Summary (end of G3) ⭐

**Status: M3 reached.** The full BSW pipeline runs end-to-end in simulation — broker → fusion →
HMI, driven by the scripted sim — with S1–S6 and the fault cases green in CI, a one-command
bring-up, and reproducible logs. M3 is the linchpin milestone ([`09-roadmap.md`](09-roadmap.md)):
it de-risks everything downstream, because the team can now demo, gather feedback, and proceed even
if hardware procurement slips. Tuning the defaults to a credible operating point is **S6**, not M3.

This summarizes what S5 consolidated and how each M3 exit criterion is met. Run book:
[`17-demo-and-run.md`](17-demo-and-run.md).

## What S5 built (consolidation)

S0–S4 delivered the components (broker+CI, fusion core, full HMI, sim+scenario runner). S5 wired
them into one demoable, reproducible pipeline and closed the remaining gaps:

1. **End-to-end over the broker, proven two ways.**
   - A **broker-free integration shim** ([`tests/test_integration_shim.py`](../tests/test_integration_shim.py))
     runs the real `FusionService` and the real scenario wire stream over an in-process loopback
     bus ([`tests/_loopback.py`](../tests/_loopback.py)) and asserts the wired path
     (publisher → bus → fusion routing → retained `bsw/zone/#` → subscriber) produces the **same
     outcomes as the in-process L3 suite**, for TC-S1..S6 + F1/F2/F3/F5. Deterministic → runs in CI
     on every push.
   - A **broker-backed test** ([`tests/test_integration_broker.py`](../tests/test_integration_broker.py))
     does the same over real paho + TCP against a running broker + fusion; it self-skips locally and
     **fails the CI integration job** if the shipped compose stack is broken.
2. **Transport refactor for a single code path.** The MQTT routing/tick logic moved out of
   `__main__.py` into a broker-agnostic [`FusionService`](../services/fusion-engine/fusion/service.py);
   `__main__` is now just the paho client + real-time loop + LWT + heartbeat. The same service runs
   under a real broker and under the shim — no sim-vs-real fork ([ADR-0005](adr/ADR-0005-sim-real-parity.md)).
   The live publisher and the shim also share **one** per-tick wire stream (`sim.scenario_tick_messages`).
3. **HMI↔fusion command loop closed.** Fusion now subscribes `bsw/cmd/#` and honors
   `set_threshold` / `enable_zone` / `disable_zone` / `reload_config` (04 §4.3.6, 05 §5.8). The S3
   HMI settings view already published these; fusion ignored them. This is also the lever S6 tuning
   needs. (L2: [`test_commands.py`](../services/fusion-engine/tests/test_commands.py).)
4. **One-command bring-up.** `docker compose up` starts broker + fusion; `--profile hmi` also serves
   the built HMI at `:8080` (Dockerfiles for both; `config/` and `logs/` mounted for live reload /
   replay).
5. **Reproducible logs (11 §11.6).** A run writes `logs/events.jsonl`; replaying the same scenario
   yields byte-identical logs and identical metrics — enforced by
   [`test_reproducibility.py`](../tests/test_reproducibility.py).
6. **Indicative latency.** `tools/latency_observer.py` measures the danger-path on a `--live` run at
   a single observer clock; `tools/scenario_runner.py --latency` prints an indicative figure from
   the deterministic sim (S1 approach → ~100 ms, within the 80–150 ms danger-path budget, 03 §3.5).
   Headline latency stays an **L4 bench** measurement (11 §11.2, 14 §P2 #6).

## M3 exit criteria — evidence

| Exit criterion (16 §16.6 / 11 §11.7) | Status | Evidence |
|---|---|---|
| S1–S6 + fault cases green in CI/sim | ✅ | L3 [`test_scenarios.py`](../tests/test_scenarios.py) + shim [`test_integration_shim.py`](../tests/test_integration_shim.py) |
| Live path matches in-process outcomes (broker→fusion→bsw/zone) | ✅ | shim (every push) + broker job ([ci.yml](../.github/workflows/ci.yml) `integration`) |
| Full pipeline demoable (broker → fusion → HMI, scripted sim) | ✅ | [`17-demo-and-run.md`](17-demo-and-run.md) §2–4; one-command compose |
| Boot **warming-up** screen (NFR-12) | ✅ | HMI liveness ([liveness.ts](../apps/hmi/src/liveness.ts)); demo §5 |
| **TC-F4** kill fusion → **SIGNAL LOST** within freshness window | ✅ | LWT+heartbeat (fusion) + liveness clock (HMI); demo §5 |
| Logs replay reproducibly | ✅ | [`test_reproducibility.py`](../tests/test_reproducibility.py) (byte-identical + identical metrics) |
| Defaults tuned to a credible operating point | ⏭ S6 | explicitly out of M3; the `bsw/cmd` sweep lever now exists |

## Scenario / fault-case coverage (11 §11.4)

| TC | Where it's proven |
|----|-------------------|
| TC-S1 pull-away FRONT_RIGHT | L3 `test_TC_S1` + shim `live_path_matches[S1]` |
| TC-S2 right-turn squeeze | L3 `test_TC_S2` + shim `test_live_S2…` + broker job (S2) |
| TC-S3 left lane change | L3 `test_TC_S3` + shim `[S3]` |
| TC-S4 reversing | L3 `test_TC_S4` + shim `[S4]` + broker job (S4) |
| TC-S5 dense crawl | L3 `test_TC_S5` + shim `[S5]` |
| TC-S6 parked standby | L3 `test_TC_S6` + shim `[S6]` |
| TC-F1 sensor unplugged → UNKNOWN | L3 `test_TC_F1` + shim `test_live_F1…` |
| TC-F2 boundary jitter (debounce holds) | L3 `test_TC_F2` + shim `[F2]` finals match |
| TC-F3 VRU vs vehicle | L3 `test_TC_F3` + shim `test_live_F3…` |
| TC-F4 compute freeze → SIGNAL LOST | HMI liveness unit tests + live kill demo (17 §5) — needs broker+HMI, not a pytest |
| TC-F5 group-fire ~½ rate/sensor | L3 `test_TC_F5` + shim `test_live_F5…` (counts over the wire) |

## Test inventory

`pytest -q tests/ services/fusion-engine/tests` → **124 passed, 2 skipped** (the broker-backed test,
which runs in the CI `integration` job / a local `docker compose up`).

- L1 contract: 26 · L2 fusion (incl. bsw/cmd): 47 · L3 scenarios: 12 + tool cores: 10 ·
  L3 integration shim: 14 · reproducibility: 11 · eval-figure: 4. HMI unit tests (Node): 26 (`cd apps/hmi && npm test`).

## CI approach (decision)

Two jobs ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)):
- **`tests`** — L1/L2/L3 + the broker-free integration shim + reproducibility. No broker, no Docker,
  fully deterministic; the shim gives end-to-end wiring coverage on every push.
- **`integration`** — brings up the shipped `deploy/docker-compose.yml` (broker + fusion) and runs
  the broker-backed test over real TCP with `BSW_REQUIRE_BROKER=1` so a broken stack fails the job.

Rationale: the shim makes the live path a first-class, deterministic CI check without infra, while
the compose job validates the **actual deliverable** (the compose file + Dockerfiles) end-to-end.

## Known limitations / next (S6+)

- **Headline detection & latency are L4 bench**, not L3 sim (the sim derives detection from geometry
  — 11 §11.2, 14 §P2 #6). The sim numbers here are indicative/regression only.
- **Defaults are not yet tuned** (NFR-09 false-alarm/sensitivity sweet spot) — that's S6, using the
  now-functional `bsw/cmd/set_threshold` sweep and the reproducible logs.
- **TC-F4 is verified by live demo + HMI unit tests**, not a single automated end-to-end test
  (it spans the broker + a browser). Documented in the run book.
- Firmware (ESP32) remains the G4 track and never gated this milestone.
