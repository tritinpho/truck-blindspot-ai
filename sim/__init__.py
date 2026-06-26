"""Geometric simulator + deterministic scenario runner (the Python side of 08-simulation.md).

Emits the same bsw/sensor + bsw/detection messages a real rig publishes (parity, ADR-0005) and
replays scripted scenarios S1-S6 through the real fusion engine for the L3 regression suite.
"""
from .geometry import Obj, Sim
from .runner import Timeline, build, run, run_on, scenario_tick_messages
from .scenarios import Scenario, Track, by_id, scenarios

__all__ = ["Obj", "Sim", "Timeline", "build", "run", "run_on", "scenario_tick_messages",
           "Scenario", "Track", "by_id", "scenarios"]
