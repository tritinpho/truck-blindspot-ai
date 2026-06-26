// Central mutable app state. The bus writes it (on MQTT messages); the rAF loop reads it.
// One screen, one store — no reactive library needed (ADR-0009).

import type {
  Health, Lang, SensorRecord, SystemPhase, ViewName, ZoneRecord, ZoneState,
} from "./types";

export interface AudioSettings {
  volume: number;              // 0..1
  mutedUntilMono: number | null; // timed mute expiry on the local clock; null = not muted
}

export interface AppState {
  zones: Map<string, ZoneRecord>;
  sensors: Map<string, SensorRecord>;     // diagnostics raw feed (lazy-subscribed)
  lastZoneReceiptMono: number | null;     // local receipt of the freshest bsw/zone/# (ADR-0008)
  lastHeartbeatReceiptMono: number | null; // local receipt of the freshest bsw/health/fusion
  fusionFaultLatched: boolean;            // set by health status:"fault" (incl. LWT)
  sawFirstZone: boolean;                  // gates the warming-up screen (NFR-12)
  fusionHealth: Health | null;
  phase: SystemPhase;
  view: ViewName;
  lang: Lang;
  audio: AudioSettings;
  localEnabled: Map<string, boolean>;     // settings zone enable/disable overrides
  sensorMsgTimes: number[];               // local receipt times for the diagnostics rate readout
}

export function createState(zoneIds: string[]): AppState {
  return {
    zones: new Map(),
    sensors: new Map(),
    lastZoneReceiptMono: null,
    lastHeartbeatReceiptMono: null,
    fusionFaultLatched: false,
    sawFirstZone: false,
    fusionHealth: null,
    phase: "WARMING_UP",
    view: "drive",
    lang: "vi",
    audio: { volume: 0.7, mutedUntilMono: null },
    localEnabled: new Map(zoneIds.map((id) => [id, true])),
    sensorMsgTimes: [],
  };
}

/** Freshest fusion signal = the later of the last zone update and the last heartbeat. */
export function lastFusionReceipt(s: AppState): number | null {
  const a = s.lastZoneReceiptMono;
  const b = s.lastHeartbeatReceiptMono;
  if (a == null) return b;
  if (b == null) return a;
  return Math.max(a, b);
}

/** Snapshot of the latest wire state per zone (what the scene/selectors consume). */
export function zoneStates(s: AppState): Map<string, ZoneState> {
  const m = new Map<string, ZoneState>();
  for (const [id, rec] of s.zones) m.set(id, rec.state);
  return m;
}

/** Is the timed mute currently active? (clears itself when expired) */
export function isMuted(s: AppState, nowMono: number): boolean {
  if (s.audio.mutedUntilMono == null) return false;
  if (nowMono >= s.audio.mutedUntilMono) {
    s.audio.mutedUntilMono = null;
    return false;
  }
  return true;
}
