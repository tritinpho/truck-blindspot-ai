// Shared HMI types. The wire shapes mirror schemas/ (04-message-protocol.md); the HMI is a
// pure consumer of the broker (driven only by bsw/zone/#, bsw/health/#, and — for diagnostics
// only — bsw/sensor/# + bsw/detection/#).

export type Severity = "SAFE" | "CAUTION" | "DANGER" | "UNKNOWN";

export type ObjectClass =
  | "pedestrian" | "cyclist" | "motorbike" | "vehicle" | "unknown" | null;

/** bsw.zone_state/1 on bsw/zone/{zone_id} (retained) + the `standby` field fusion adds. */
export interface ZoneState {
  schema: string;
  zone_id: string;
  ts: number;
  severity: Severity;
  object_class?: ObjectClass;
  nearest_range_m?: number | null;
  source?: string;
  reason?: string;
  stale?: boolean;
  /** fusion park-standby flag (05 §5.4): keep visuals, suppress audio nagging. */
  standby?: boolean;
}

/** bsw.health/1 on bsw/health/{component}. */
export interface Health {
  schema: string;
  component: string;
  ts: number;
  status: "ok" | "degraded" | "fault";
  detail?: string;
}

/** bsw.sensor_reading/1 on bsw/sensor/{sensor_id} (diagnostics view only). */
export interface SensorReading {
  schema: string;
  sensor_id: string;
  ts: number;
  ts_kind?: string;
  modality?: string;
  present?: boolean;
  range_m?: number | null;
  confidence?: number;
  health?: "ok" | "degraded" | "fault";
}

/** Explicit startup → monitoring → fault states (ADR-0006, NFR-12). */
export type SystemPhase = "WARMING_UP" | "MONITORING" | "SIGNAL_LOST";

export type Lang = "vi" | "en";
export type ViewName = "drive" | "settings" | "diagnostics";

/** A live zone record: the wire state plus its LOCAL receipt time (ADR-0008). */
export interface ZoneRecord {
  state: ZoneState;
  receiptMono: number; // performance.now() at receipt — the local monotonic clock
}

/** A live sensor record for the diagnostics raw feed. */
export interface SensorRecord {
  reading: SensorReading;
  receiptMono: number;
}
