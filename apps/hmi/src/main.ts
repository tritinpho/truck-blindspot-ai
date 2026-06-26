import mqtt from "mqtt";
import zonesRaw from "../../../config/zones.example.json";

// S1 vertical slice: subscribe to bsw/zone/# and tint a config-driven top-view by severity.
// The full HMI (icons, audio, liveness clock, settings) lands in S3 (06-hmi-design.md).

type Severity = "SAFE" | "CAUTION" | "DANGER" | "UNKNOWN";
type Zone = { id: string; enabled: boolean; polygon_norm: number[][] };
type ZonesConfig = { truck_outline_norm: number[][]; zones: Zone[] };

const zonesConfig = zonesRaw as unknown as ZonesConfig;

const FILL: Record<Severity, string> = {
  SAFE: "rgba(70,84,102,0.25)",
  CAUTION: "rgba(240,170,40,0.55)",
  DANGER: "rgba(225,60,55,0.78)",
  UNKNOWN: "rgba(120,124,134,0.30)",
};

const BROKER = import.meta.env.VITE_BROKER_WS ?? "ws://localhost:9001";
const severity = new Map<string, Severity>();

const canvas = document.getElementById("scene") as HTMLCanvasElement;
const ctx = canvas.getContext("2d")!;

function fit(): void {
  const s = Math.max(320, Math.min(window.innerWidth, window.innerHeight) - 24);
  canvas.width = s;
  canvas.height = s;
  render();
}

function trace(points: number[][]): void {
  const { width: W, height: H } = canvas;
  ctx.beginPath();
  points.forEach(([x, y], i) => (i ? ctx.lineTo(x * W, y * H) : ctx.moveTo(x * W, y * H)));
  ctx.closePath();
}

function centroid(points: number[][]): [number, number] {
  const n = points.length;
  const x = points.reduce((a, p) => a + p[0], 0) / n;
  const y = points.reduce((a, p) => a + p[1], 0) / n;
  return [x, y];
}

function label(text: string, cx: number, cy: number, px: number, color: string): void {
  ctx.fillStyle = color;
  ctx.font = `${Math.round(px)}px system-ui`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, cx * canvas.width, cy * canvas.height);
}

function render(): void {
  const { width: W, height: H } = canvas;
  ctx.clearRect(0, 0, W, H);

  for (const z of zonesConfig.zones) {
    if (!z.enabled) continue;
    const sev = severity.get(z.id) ?? "UNKNOWN";
    trace(z.polygon_norm);
    ctx.fillStyle = FILL[sev];
    ctx.fill();
    ctx.strokeStyle = "rgba(200,210,220,0.22)";
    ctx.lineWidth = 1;
    ctx.stroke();
    const [cx, cy] = centroid(z.polygon_norm);
    label(z.id, cx, cy, W * 0.016, "#aeb6c2");
  }

  trace(zonesConfig.truck_outline_norm);
  ctx.fillStyle = "rgba(38,46,58,0.96)";
  ctx.fill();
  ctx.strokeStyle = "#5b6675";
  ctx.lineWidth = 2;
  ctx.stroke();
  const [tx, ty] = centroid(zonesConfig.truck_outline_norm);
  label("CAB", tx, ty, W * 0.02, "#8a94a4");
}

const client = mqtt.connect(BROKER);
client.on("connect", () => {
  console.info(`[hmi] connected to ${BROKER}`);
  client.subscribe("bsw/zone/#");
});
client.on("message", (_topic, payload) => {
  try {
    const z = JSON.parse(payload.toString());
    if (z.zone_id && z.severity) {
      severity.set(z.zone_id, z.severity as Severity);
      render();
    }
  } catch {
    /* ignore malformed payloads */
  }
});
client.on("error", (e) => console.error("[hmi] mqtt error:", e));

window.addEventListener("resize", fit);
fit();
