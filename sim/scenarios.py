"""Scenario definitions S1-S6 + fault cases (02 §2.3, 11 §11.4). Pure data — a scenario is a set
of object tracks (where an object is, over time) plus a vehicle-context and fault knobs. The
expected OUTCOMES live with the assertions in tests/test_scenarios.py; this file just describes
the scene so it can be replayed deterministically (runner) or published live (scenario_runner).

Ranges are chosen to sit clearly inside a zone's band so severity outcomes are robust; an object
approaching from beyond a zone's depth starts SAFE (out of zone) and escalates as it enters.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Track:
    """One object: which zone it sits in, its range over time (linear between keys, held at the
    ends), and an optional class (camera/phase-2 only)."""
    zone: str
    keys: list[tuple[int, float]]  # (t_ms, range_m), ascending in t
    cls: str | None = None

    def range_at(self, t: int) -> float:
        ks = self.keys
        if t <= ks[0][0]:
            return ks[0][1]
        if t >= ks[-1][0]:
            return ks[-1][1]
        for (t0, r0), (t1, r1) in zip(ks, ks[1:]):
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                return r0 + (r1 - r0) * f
        return ks[-1][1]


@dataclass
class Scenario:
    id: str
    name: str
    tc: str                      # the 11 §11.4 test-case id
    tracks: list[Track]
    vehicle: dict | None
    duration_ms: int
    group_fire: bool = True
    noise_m: float = 0.0
    dropout: float = 0.0
    enable_camera: bool = False
    drop_after_ms: dict[str, int] = field(default_factory=dict)  # sensor_id -> unplug time
    seed: int = 12345

    def objects_at(self, sim, t: int) -> list:
        objs = []
        for tr in self.tracks:
            o = sim.place_in_zone(tr.zone, tr.range_at(t))
            o.cls = tr.cls
            objs.append(o)
        return objs

    def dropped_at(self, t: int) -> set[str]:
        return {sid for sid, t0 in self.drop_after_ms.items() if t >= t0}


def approach(zone: str, start: float, end: float, dur: int, cls: str | None = None,
             hold: float = 0.3) -> Track:
    """Object closing from `start` to `end` m over `dur`, holding `end` for the last `hold` fraction
    so the zone has time to settle before the run ends."""
    t_reach = int(dur * (1 - hold))
    return Track(zone, [(0, start), (t_reach, end), (dur, end)], cls)


def static(zone: str, r: float, dur: int, cls: str | None = None) -> Track:
    return Track(zone, [(0, r), (dur, r)], cls)


VEH_NONE = {"gear": "drive", "speed_kph": 6.0, "turn_signal": "none"}


def scenarios() -> list[Scenario]:
    return [
        # ---- S1-S6: the operational scenarios (02 §2.3) ----
        Scenario("S1", "Pull-away — motorbike in FRONT_RIGHT", "TC-S1",
                 [approach("FRONT_RIGHT", 3.0, 0.7, 4000)], VEH_NONE, 4000),

        Scenario("S2", "Right-turn squeeze — motorbike along RIGHT (signal=right)", "TC-S2",
                 [approach("RIGHT", 2.6, 0.7, 4000)],
                 {"gear": "drive", "speed_kph": 9.0, "turn_signal": "right"}, 4000),

        Scenario("S3", "Left lane change — vehicle in LEFT (signal=left)", "TC-S3",
                 [approach("LEFT", 2.0, 0.9, 4000)],
                 {"gear": "drive", "speed_kph": 25.0, "turn_signal": "left"}, 4000),

        Scenario("S4", "Reversing — pallet behind on REAR (gear=reverse)", "TC-S4",
                 [approach("REAR", 1.5, 0.5, 3500)],
                 {"gear": "reverse", "speed_kph": 3.0, "turn_signal": "none"}, 3500),

        Scenario("S5", "Dense urban crawl — RIGHT+LEFT+REAR occupied", "TC-S5",
                 [static("RIGHT", 0.7, 2500), static("LEFT", 1.2, 2500), static("REAR", 0.9, 2500)],
                 VEH_NONE, 2500),

        Scenario("S6", "Parked by a wall on LEFT (gear=park, stationary → standby)", "TC-S6",
                 [static("LEFT", 0.6, 2500)],
                 {"gear": "park", "speed_kph": 0.0, "turn_signal": "none"}, 2500),

        # ---- fault / edge cases (11 §11.4) ----
        Scenario("F1", "RIGHT ultrasonic unplugged mid-run → UNKNOWN", "TC-F1",
                 [static("RIGHT", 0.7, 3500)],
                 {"gear": "drive", "speed_kph": 9.0, "turn_signal": "right"}, 3500,
                 drop_after_ms={"right_mid": 1500}),

        Scenario("F2", "Boundary jitter at danger_m — debounce must hold", "TC-F2",
                 [static("RIGHT", 1.05, 4000)], VEH_NONE, 4000,
                 group_fire=False, noise_m=0.12, seed=7),

        # F3 is run twice by the test (pedestrian vs vehicle) — phase-2 camera path.
        Scenario("F3", "VRU vs vehicle at the same range (phase-2 camera)", "TC-F3",
                 [static("RIGHT", 1.2, 1500, cls="pedestrian")], VEH_NONE, 1500,
                 group_fire=False, enable_camera=True),
    ]


def by_id() -> dict[str, Scenario]:
    return {s.id: s for s in scenarios()}
