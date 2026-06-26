# apps/hmi — in-cabin HMI (React + TS + Canvas, Chromium kiosk)

Subscribes to retained `bsw/zone/#` over MQTT-WebSocket and renders the top-view truck with
color-coded zones, icons, audio, and a liveness indicator. Spec:
[06-hmi-design.md](../../docs/06-hmi-design.md), rationale [ADR-0003](../../docs/adr/ADR-0003-hmi-stack.md).

**Status:** S0 skeleton — connects to `ws://localhost:9001` and logs traffic. Rendering in S3.

```bash
npm install
npm run dev          # http://localhost:5173 ; start the broker via deploy/docker-compose.yml
```

Broker override: `VITE_BROKER_WS=ws://<host>:9001`.
