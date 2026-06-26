# services/ — Python services on the Raspberry Pi

- `fusion-engine/` — sensor → zone severity engine (the core "bộ xử lý trung tâm"; S1–S2).
- `vehicle-adapter/` — GPIO / OBD-II → `bsw/vehicle` context (optional; degrades gracefully; deferred).
