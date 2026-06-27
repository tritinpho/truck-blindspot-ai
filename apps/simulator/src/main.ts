import mqtt from "mqtt";

// S0 skeleton: connect to the broker. The interactive drag-drop web scene-editor was deferred as a
// stretch (16 §16.7); the M3 sim is the Python geometric sim + scenario runner (sim/ +
// tools/scenario_runner.py + tools/sim_demo.py), which emits the SAME bsw/sensor + bsw/vehicle
// contract a real rig does (parity, ADR-0005). For now this only proves a browser producer can
// reach the broker — swap a scene editor in here if the interactive aid is built later.
const URL = import.meta.env.VITE_BROKER_WS ?? "ws://localhost:9001";
const client = mqtt.connect(URL);

client.on("connect", () => {
  console.info(`[sim] connected to ${URL} — ready (no scene yet)`);
});
client.on("error", (err) => console.error("[sim] mqtt error:", err));
