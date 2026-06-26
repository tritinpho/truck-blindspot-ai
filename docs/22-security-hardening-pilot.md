# 22 — Security hardening for the vehicle pilot

**Status:** checklist (pre-pilot). The dev/demo stack runs an **anonymous** MQTT broker by design
(ADR-0002, `deploy/mosquitto/mosquitto.conf`, 03 §3.8, 10 #15) — it keeps sim/real parity friction
low and has no secrets to leak. That posture is fine for a bench and the M1–M3 milestones, but it
**must be closed before any on-vehicle deployment**. This document is the drop-in checklist and the
threat model behind it. The companion `deploy/mosquitto/aclfile.example` is a ready-to-edit ACL.

This is a **safety** requirement, not only a security one: on an open broker any node can forge the
inputs the central processor and the in-cabin display trust, and several of those forgeries defeat
the warning function directly.

## Threat model (anonymous broker)

With `allow_anonymous true` every connected node is fully trusted. The safety-relevant paths, worst
first:

| # | Path | Topic | Effect |
|---|------|-------|--------|
| 1 | **Command injection** | `bsw/cmd/fusion` | `disable_zone RIGHT` silently turns off the deadliest zone (VN right-turn squeeze); `set_threshold` can blind a zone (tiny danger_m) or over-sensitize it (alarm fatigue). Highest leverage. |
| 2 | **Sensor spoof — fake clear** | `bsw/sensor/{id}` | `present:false` for a zone that actually has an object → fusion reads SAFE while a motorbike is there. Silent, dangerous. |
| 3 | **Health / LWT spoof** | `bsw/health/fusion` | `status:"fault"` forces the HMI to SIGNAL_LOST (whole map UNKNOWN). Fail-safe, but a denial of the advisory function (nuisance DoS). |
| 4 | **Retained zone spoof** | `bsw/zone/{id}` | Inject an attacker-controlled severity to the HMI. Fusion republishes retained at 10 Hz so a live spoof is transient, but a retained message on a zone fusion is **not** currently publishing can persist on the broker. |
| 5 | **Malformed input** | any | A wrong-typed field crashing a consumer. **Already hardened in code** (sensor `range_m`, vehicle `speed_kph`, HMI `severity`/`nearest_range_m`) — see `engine.py`, `service.py`, `apps/hmi/src/validate.ts`. Keep it: it is defense-in-depth, necessary even with auth. |

The code-level trust-boundary hardening addresses #5. **Auth + ACLs are what close #1–#4** — input
validation cannot, because these messages are well-formed; the problem is that an untrusted node is
allowed to send them at all.

## Pilot checklist

- [ ] **Disable anonymous access.** `allow_anonymous false` + a `password_file` with **one
  credential per node** (`fusion`, `hmi`, `vehicle`, and each sensor). Create with
  `mosquitto_passwd`.
- [ ] **Per-client ACLs — least privilege.** Enable `acl_file` and start from
  `deploy/mosquitto/aclfile.example`. The intent:
  - `fusion` — the **only** publisher of `bsw/zone/#` and `bsw/health/fusion`; subscribes to
    `bsw/sensor/#`, `bsw/detection/#`, `bsw/vehicle`, `bsw/cmd/#`.
  - `hmi` — subscribes to `bsw/zone/#`, `bsw/health/#`, and the diagnostics feed; the **only**
    publisher of `bsw/cmd/fusion`.
  - each **sensor node** — may publish **only its own** `bsw/sensor/{id}` (+ `bsw/health/{id}`);
    no subscribe.
  - `vehicle` adapter — publishes `bsw/vehicle` (+ its health) only.
  - This alone neutralizes #1 (only HMI may command), #2/#4 (only fusion may publish zone state;
    a sensor can only forge **its own** reading, which fusion already fuses/ages), and bounds #3.
- [ ] **TLS on both listeners.** `1883 → 8883` (mqtts) and `9001 → wss` with a project CA; pin the
  CA in fusion and in the HMI build (`VITE_BROKER_WS=wss://…`). Prevents passive sniffing and
  on-path tampering inside the vehicle network.
- [ ] **Network isolation.** Bind the broker to the vehicle's internal segment/VLAN; do not expose
  1883/9001/8883 beyond it. (The shipped `docker-compose.yml` publishes the ports for host-driven
  scenarios on the bench — do not carry that mapping onto the vehicle unchanged.)
- [ ] **Retained-message hygiene.** With the ACL above only `fusion` can set retained `bsw/zone/#`.
  Broker `persistence` stays `false` (already), so a spoofed retained message cannot survive a
  broker restart.
- [ ] **Keep the code trust-boundary hardening** (untrusted input sanitized) as defense-in-depth.
- [ ] **No secrets in git.** `password_file`, TLS keys, and a filled-in `aclfile` are deployment
  artifacts, not committed. The files in `deploy/mosquitto/` are templates/examples only.
- [ ] **Rotate** node credentials and the CA at pilot start and on any node replacement.

## What does NOT change

The application code is unchanged by any of this — fusion, the HMI, sensors, and the simulator all
speak the same frozen contracts (ADR-0005) over an authenticated/encrypted broker exactly as over
the dev one. Hardening is purely broker configuration plus the credentials/CA the nodes present.

## References

ADR-0002 (message bus) · 03 §3.8 (deployment) · 10 #15 (deferred items) · 13 (privacy & ethics) ·
`deploy/mosquitto/mosquitto.conf` · `deploy/mosquitto/aclfile.example`.
