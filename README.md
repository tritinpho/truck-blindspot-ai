<a id="top"></a>

# 🚛 Hệ thống Cảnh báo Điểm mù cho Xe tải · BSW

**🇻🇳 Tiếng Việt** · [🇬🇧 English ↓](#english)

> *Blind-Spot Warning (BSW)* — phần **phần mềm** của hệ thống cảnh báo điểm mù cho xe tải.

Xe tải có những vùng **điểm mù** rất rộng ở đầu xe, hai bên hông và phía sau. Trong giao thông Việt Nam — nơi xe máy thường đi sát xe lớn — chỉ nhìn gương là không đủ, nguy hiểm nhất là lúc **rẽ phải, chuyển làn và lùi xe**.

Hệ thống này phát hiện xe máy, người đi bộ và vật cản trong các vùng điểm mù, rồi cảnh báo tài xế bằng **màn hình nhìn từ trên xuống** (tô màu theo từng vùng) và **âm thanh** trong cabin — để tài xế biết **nguy hiểm đang ở đâu**, chứ không chỉ biết là *có* nguy hiểm.

Đây là phần mềm của đề tài nghiên cứu cấp trường *"Nghiên cứu giải pháp cảnh báo điểm mù cho xe tải để giảm thiểu tai nạn giao thông"*.

> **Trạng thái:** ✅ Toàn bộ pipeline đã chạy thông trong mô phỏng (broker → fusion → HMI). Hợp đồng bản tin đã "đóng băng". Bước tiếp theo là tích hợp cảm biến thật (G4). Chi tiết: [`docs/18-m3-summary.md`](docs/18-m3-summary.md).

## Hệ thống hoạt động thế nào

```
Cảm biến / Trình mô phỏng  ──►  MQTT (Mosquitto)  ──►  Fusion Engine  ──►  HMI trong cabin
 siêu âm · radar · camera        bus tin nhắn          (Python)           màn hình + âm thanh
```

Điểm quan trọng: **cùng một phần mềm chạy được trên cả phần cứng thật lẫn trình mô phỏng** — cả hai nói chung một giao thức bản tin qua MQTT. Nhờ vậy nhóm có thể phát triển, demo và đánh giá ngay cả khi mô hình xe chưa lắp xong ([ADR-0005](docs/adr/ADR-0005-sim-real-parity.md)).

## Công nghệ sử dụng

| Thành phần | Công nghệ |
|------------|-----------|
| Máy tính trung tâm | Raspberry Pi 4 (Linux) |
| Nút cảm biến | ESP32 + HC-SR04 (siêu âm); firmware C/C++ |
| Bus tin nhắn | MQTT — Mosquitto |
| Fusion engine (bộ xử lý trung tâm) | Python 3 · paho-mqtt |
| HMI (màn hình cabin) | TypeScript · Vite · Canvas · Web Audio |
| Trình mô phỏng | Python (`sim/`) hoặc web (vanilla TS) |
| Ghi log (hộp đen) | SQLite + JSONL |
| Đóng gói · triển khai | Docker Compose (dev) · systemd (Pi) |

Lý do chọn từng công nghệ: xem [`docs/07-tech-stack.md`](docs/07-tech-stack.md) và các [ADR](docs/adr/).

## Yêu cầu

- **Docker** + **Docker Compose** — cách nhanh nhất để chạy thử cả hệ thống.
- **Python 3.11+** — chạy fusion engine, các script và trình mô phỏng.
- **Node.js LTS** — chỉ cần khi phát triển HMI / web simulator.

## Cài đặt & chạy thử

### Cách nhanh nhất — demo một lệnh

Cần Docker. Lệnh này dựng broker + fusion + HMI, mở trình duyệt và chạy một kịch bản có thuyết minh (S1 / S2 + lỗi cảm biến / S4 / S6):

```bash
python tools/demo.py        # → mở http://localhost:8080
# Ctrl-C để dừng · python tools/demo.py --down để gỡ stack
```

### Chạy từng phần

```bash
# 1. Dựng broker + fusion
docker compose -f deploy/docker-compose.yml up -d

# 2. Bơm một kịch bản vào broker (đúng bản tin mà xe thật phát ra)
python tools/scenario_runner.py S2 --live          # tình huống rẽ phải → cảnh báo bên PHẢI

# 3. Mở HMI
docker compose -f deploy/docker-compose.yml --profile hmi up -d   # http://localhost:8080
```

Muốn xem hệ thống "báo lỗi rõ ràng": tắt fusion (`docker compose -f deploy/docker-compose.yml kill fusion`) — bản đồ sẽ chuyển sang **SIGNAL LOST** trong ~1 giây. Run book đầy đủ: [`docs/17-demo-and-run.md`](docs/17-demo-and-run.md).

### Kiểm thử (không cần phần cứng, không cần broker)

```bash
pip install -r tests/requirements.txt
pytest -q tests/ services/fusion-engine/tests
```

### Phát triển HMI (hot reload)

```bash
cd apps/hmi
npm install
npm run dev          # http://localhost:5173
npm test             # kiểm thử phần logic an toàn (node --test)
```

## Cấu trúc dự án

| Thư mục | Nội dung |
|---------|----------|
| [`apps/hmi/`](apps/hmi/) | Màn hình trong cabin — TypeScript + Canvas |
| [`apps/simulator/`](apps/simulator/) | Trình mô phỏng web (kéo-thả, đang phát triển) |
| [`services/fusion-engine/`](services/fusion-engine/) | Bộ xử lý trung tâm — Python |
| [`services/vehicle-adapter/`](services/vehicle-adapter/) | Đọc tín hiệu xe (rẽ / lùi / tốc độ), tùy chọn |
| [`sim/`](sim/) | Trình mô phỏng + bộ chạy kịch bản — Python |
| [`firmware/sensor-node-esp32/`](firmware/sensor-node-esp32/) | Firmware ESP32 (hợp đồng + checklist) |
| [`schemas/`](schemas/) | JSON Schema cho các bản tin |
| [`config/`](config/) | Cấu hình mẫu cho vùng & cảm biến |
| [`deploy/`](deploy/) | Docker Compose + cấu hình Mosquitto |
| [`tools/`](tools/) | Demo, chạy kịch bản, script đánh giá |
| [`tests/`](tests/) | Kiểm thử hợp đồng + tích hợp |
| [`docs/`](docs/) | Toàn bộ tài liệu: kiến trúc, ADR, hướng dẫn nhóm |

## Tài liệu

Hệ thống làm theo nguyên tắc **hợp đồng trước** (contract-first): [`schemas/`](schemas/) và [`docs/04-message-protocol.md`](docs/04-message-protocol.md) là nguồn chân lý. Bất kỳ thành phần nào (cảm biến, fusion, HMI, mô phỏng) cũng có thể làm độc lập miễn là tuân thủ hợp đồng đó.

Hướng dẫn theo từng nhóm (tiếng Việt):

| Bạn thuộc nhóm | Đọc trước |
|----------------|-----------|
| **Tổng quan / mới vào** | [`docs/01-overview.md`](docs/01-overview.md) → [`docs/03-architecture.md`](docs/03-architecture.md) |
| **Phần cứng · Firmware** | [`docs/26`](docs/26-firmware-bat-dau-nhanh.md) → [`docs/24`](docs/24-huong-dan-lap-dat-phan-cung.md) |
| **Đánh giá · Báo cáo** | [`docs/25`](docs/25-huong-dan-danh-gia.md) |
| **Phối hợp giữa các nhóm** | [`docs/23`](docs/23-ban-giao-tich-hop.md) |

## Giấy phép

Bản quyền — đang chờ quyết định về sở hữu trí tuệ (*all rights reserved*). Xem [`LICENSE`](LICENSE).

---

<a id="english"></a>

# 🚛 Truck Blind-Spot Warning System · BSW

**🇬🇧 English** · [🇻🇳 Tiếng Việt ↑](#top)

> *Blind-Spot Warning (BSW)* — the **software** side of a truck blind-spot warning system.

Trucks have wide **blind spots** at the front, both sides, and the rear. In Vietnamese traffic — where motorbikes ride very close to large vehicles — mirrors alone aren't enough, and the most dangerous moments are **right turns, lane changes, and reversing**.

This system detects motorbikes, pedestrians, and obstacles in those blind-spot zones, then warns the driver with a **top-view display** (color-coded per zone) and **audio alerts** in the cabin — so the driver knows **where** the danger is, not just *that* there is one.

It is the software realization of the university R&D project *"Researching a blind-spot warning solution for trucks to reduce traffic accidents."*

> **Status:** ✅ The full pipeline runs end-to-end in simulation (broker → fusion → HMI). The message contracts are frozen. Next up is real-sensor bring-up (G4). Details: [`docs/18-m3-summary.md`](docs/18-m3-summary.md).

## How it works

```
Sensors / Simulator  ──►  MQTT (Mosquitto)  ──►  Fusion Engine  ──►  In-cabin HMI
 ultrasonic · radar · cam    message bus          (Python)          display + audio
```

The key idea: **the same software runs on real hardware and on the simulator** — both speak one message protocol over MQTT. That lets the team build, demo, and evaluate the system before the physical model is finished ([ADR-0005](docs/adr/ADR-0005-sim-real-parity.md)).

## Tech stack

| Component | Technology |
|-----------|------------|
| Central compute | Raspberry Pi 4 (Linux) |
| Sensor nodes | ESP32 + HC-SR04 (ultrasonic); C/C++ firmware |
| Message bus | MQTT — Mosquitto |
| Fusion engine | Python 3 · paho-mqtt |
| HMI (cabin display) | TypeScript · Vite · Canvas · Web Audio |
| Simulator | Python (`sim/`) or web (vanilla TS) |
| Logging (black box) | SQLite + JSONL |
| Packaging · deploy | Docker Compose (dev) · systemd (Pi) |

Rationale for each choice: see [`docs/07-tech-stack.md`](docs/07-tech-stack.md) and the [ADRs](docs/adr/).

## Requirements

- **Docker** + **Docker Compose** — the fastest way to run the whole system.
- **Python 3.11+** — to run the fusion engine, tools, and simulator.
- **Node.js LTS** — only for HMI / web-simulator development.

## Install & run

### Fastest path — one-command demo

Needs Docker. This brings up broker + fusion + HMI, opens the browser, and plays a narrated scenario (S1 / S2 + sensor fault / S4 / S6):

```bash
python tools/demo.py        # → opens http://localhost:8080
# Ctrl-C to stop · python tools/demo.py --down to remove the stack
```

### Run the pieces by hand

```bash
# 1. Bring up broker + fusion
docker compose -f deploy/docker-compose.yml up -d

# 2. Drive a scenario over the broker (the same wire messages a real rig emits)
python tools/scenario_runner.py S2 --live          # right-turn squeeze → RIGHT DANGER

# 3. Open the HMI
docker compose -f deploy/docker-compose.yml --profile hmi up -d   # http://localhost:8080
```

To see it fail loud, kill fusion (`docker compose -f deploy/docker-compose.yml kill fusion`) — the map degrades to **SIGNAL LOST** within ~1 s. Full run book: [`docs/17-demo-and-run.md`](docs/17-demo-and-run.md).

### Test (no hardware, no broker)

```bash
pip install -r tests/requirements.txt
pytest -q tests/ services/fusion-engine/tests
```

### HMI development (hot reload)

```bash
cd apps/hmi
npm install
npm run dev          # http://localhost:5173
npm test             # unit tests on the safety-critical logic (node --test)
```

## Project layout

| Directory | Contents |
|-----------|----------|
| [`apps/hmi/`](apps/hmi/) | In-cabin display — TypeScript + Canvas |
| [`apps/simulator/`](apps/simulator/) | Web simulator (drag-and-drop, in progress) |
| [`services/fusion-engine/`](services/fusion-engine/) | Central processor — Python |
| [`services/vehicle-adapter/`](services/vehicle-adapter/) | Vehicle signals (turn / reverse / speed), optional |
| [`sim/`](sim/) | Simulator + scenario runner — Python |
| [`firmware/sensor-node-esp32/`](firmware/sensor-node-esp32/) | ESP32 firmware (contract + checklist) |
| [`schemas/`](schemas/) | JSON Schemas for the messages |
| [`config/`](config/) | Example zone & sensor configuration |
| [`deploy/`](deploy/) | Docker Compose + Mosquitto config |
| [`tools/`](tools/) | Demo, scenario runner, evaluation scripts |
| [`tests/`](tests/) | Contract + integration tests |
| [`docs/`](docs/) | All documentation: architecture, ADRs, team guides |

## Documentation

The system is **contract-first**: [`schemas/`](schemas/) and [`docs/04-message-protocol.md`](docs/04-message-protocol.md) are the source of truth. Any component (sensor node, fusion, HMI, simulator) can be built independently as long as it honors those contracts.

Good starting points:

- **New here?** [`docs/01-overview.md`](docs/01-overview.md) → [`docs/03-architecture.md`](docs/03-architecture.md)
- **Why the stack is what it is:** the [ADRs](docs/adr/)
- **Run & demo:** [`docs/17-demo-and-run.md`](docs/17-demo-and-run.md)

> Team-facing guides (`docs/23`–`docs/26`) are written in Vietnamese — see the table in the Vietnamese section above.

## License

Proprietary — all rights reserved, pending an IP decision. See [`LICENSE`](LICENSE).
