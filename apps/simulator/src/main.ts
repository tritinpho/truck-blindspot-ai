import mqtt from "mqtt";

// S0 skeleton: connect to the broker. The scene editor and scripted scenario
// publishing — the SAME bsw/sensor + bsw/vehicle contract a real rig emits
// (sim/real parity, ADR-0005) — land in S2/S4. For now this only proves the
// producer can reach the broker.
const URL = import.meta.env.VITE_BROKER_WS ?? "ws://localhost:9001";
const client = mqtt.connect(URL);

client.on("connect", () => {
  console.info(`[sim] connected to ${URL} — ready (no scene yet)`);
});
client.on("error", (err) => console.error("[sim] mqtt error:", err));
