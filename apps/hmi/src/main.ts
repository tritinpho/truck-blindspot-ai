import mqtt from "mqtt";

// S0 skeleton: connect to the broker over WebSocket and log zone/health traffic.
// The top-view canvas, audio engine, and liveness clock land in S3
// (06-hmi-design.md, ADR-0006). For now this only proves the MQTT-WS seam.
const URL = import.meta.env.VITE_BROKER_WS ?? "ws://localhost:9001";
const client = mqtt.connect(URL);

client.on("connect", () => {
  console.info(`[hmi] connected to ${URL}`);
  client.subscribe("bsw/zone/#");
  client.subscribe("bsw/health/#");
});
client.on("message", (topic, payload) => {
  console.info(`[hmi] ${topic}`, payload.toString());
});
client.on("error", (err) => console.error("[hmi] mqtt error:", err));
