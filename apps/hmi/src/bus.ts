// MQTT-over-WebSocket transport. The HMI is a pure broker consumer (06 §6.5): it subscribes to
// retained bsw/zone/# (its data) and bsw/health/# (liveness), and — only while Diagnostics is
// open — to bsw/sensor/# + bsw/detection/# (the raw feed). It publishes bsw/cmd/fusion (FR-12).
//
// CLOCK DISCIPLINE (ADR-0008): every receipt is stamped with the LOCAL monotonic clock
// (performance.now()), never the message `ts`. That local time is what the liveness clock ages.

import mqtt from "mqtt";
import type { Health, SensorReading, ZoneState } from "./types";
import type { AppState } from "./store";

const DIAG_TOPICS = ["bsw/sensor/#", "bsw/detection/#"];

export class Bus {
  private client: mqtt.MqttClient;
  private state: AppState;
  private diagSubscribed = false;

  constructor(url: string, state: AppState) {
    this.state = state;
    this.client = mqtt.connect(url);

    this.client.on("connect", () => {
      console.info(`[hmi] connected to ${url}`);
      this.client.subscribe(["bsw/zone/#", "bsw/health/#"]);
    });
    this.client.on("message", (topic, payload) => this.onMessage(topic, payload));
    this.client.on("error", (e) => console.error("[hmi] mqtt error:", e));
  }

  private onMessage(topic: string, payload: Uint8Array): void {
    let data: unknown;
    try {
      data = JSON.parse(new TextDecoder().decode(payload));
    } catch {
      return; // ignore malformed payloads
    }
    const now = performance.now();
    const parts = topic.split("/");

    if (parts[1] === "zone") {
      const z = data as ZoneState;
      if (!z.zone_id || !z.severity) return;
      this.state.zones.set(z.zone_id, { state: z, receiptMono: now });
      this.state.lastZoneReceiptMono = now;
      this.state.sawFirstZone = true;
      // a zone update proves fusion is alive — clear any latched fault
      this.state.fusionFaultLatched = false;
      return;
    }

    if (parts[1] === "health") {
      const h = data as Health;
      if (h.component === "fusion") {
        this.state.fusionHealth = h;
        this.state.lastHeartbeatReceiptMono = now;
        // an explicit fault (incl. the broker Last-Will) trips SIGNAL_LOST at once (ADR-0006)
        this.state.fusionFaultLatched = h.status === "fault";
      }
      return;
    }

    if (parts[1] === "sensor" || parts[1] === "detection") {
      const r = data as SensorReading;
      const id = r.sensor_id ?? parts[2];
      if (!id) return;
      this.state.sensors.set(id, { reading: r, receiptMono: now });
      this.state.sensorMsgTimes.push(now);
      return;
    }
  }

  /** Subscribe to the raw feed only while Diagnostics is open (keeps the drive path lean). */
  setDiagnostics(on: boolean): void {
    if (on && !this.diagSubscribed) {
      this.client.subscribe(DIAG_TOPICS);
      this.diagSubscribed = true;
    } else if (!on && this.diagSubscribed) {
      this.client.unsubscribe(DIAG_TOPICS);
      this.diagSubscribed = false;
      this.state.sensors.clear();
      this.state.sensorMsgTimes.length = 0;
    }
  }

  /** Publish a bsw.cmd/1 to the fusion engine (set_threshold / enable_zone / …). QoS 1. */
  publishCmd(op: string, args: Record<string, unknown>): void {
    const msg = { schema: "bsw.cmd/1", ts: Date.now(), ts_kind: "epoch_ms", op, args };
    this.client.publish("bsw/cmd/fusion", JSON.stringify(msg), { qos: 1 });
  }
}
