# 23 — Bàn giao & phối hợp giữa các nhóm

**Mục đích.** Liệt kê đúng những thứ các nhóm cần thống nhất. Phần lớn đã được "đóng băng"
trong hợp đồng tin nhắn (tag `m1-contracts-frozen`), nên việc còn lại rất ít.

## 1. Không cần thống nhất tech stack
Mỗi nhóm giữ ngôn ngữ và công cụ riêng:
- Phần mềm: Python (fusion) + TypeScript (HMI) + Python (mô phỏng).
- Firmware: C/C++ trên ESP32.

Điểm chung **bắt buộc** duy nhất: nói chuyện qua **MQTT**, dữ liệu là **JSON** rút gọn,
broker là **Mosquitto** trên Pi. Hết. Firmware chỉ cần một thư viện MQTT
(`PubSubClient` hoặc `esp-mqtt`).

## 2. Biến dùng chung (chỉ 2 thứ)
1. **Tên cảm biến `sensor_id`** — file [`../config/sensors.example.json`](../config/sensors.example.json).
   Đây là "từ điển chung" duy nhất. Firmware phải gửi đúng các tên này (vd `right_mid`),
   chữ thường, và tên phải **trùng** với nhánh cuối của topic (`bsw/sensor/right_mid`).
   Firmware **không** biết "zone" — Pi tự ánh xạ `sensor_id → zone`.
2. **Bố trí vật lý** — polygon trong [`../config/zones.example.json`](../config/zones.example.json),
   cùng `mount`, `fire_group`, `max_range_m`. Đây là mô hình của xe thật.
   **Nhóm phần cứng quyết vị trí gắn và thứ tự bắn thật; phần mềm chỉ chép lại vào config.**
   Khi gắn cảm biến lên xe thật mà khác layout mẫu → phải sửa config cho khớp.

Mọi thứ khác trên đường truyền (định dạng tin, đơn vị **mét** / **mili-giây**,
`present=false ⇒ range_m=null`, `ts_kind=monotonic_ms`, QoS 0 / không retain,
heartbeat + Last-Will) đã **đóng băng, không bàn lại**. Đưa nhóm firmware đọc
[`20-firmware-contract-checklist.md`](20-firmware-contract-checklist.md) và tự kiểm bằng
[`../tools/validate_message.py`](../tools/validate_message.py).

## 3. Việc cần phối hợp ngoài hợp đồng
Hợp đồng không ghi được mấy thứ vật lý này — phải trao đổi trực tiếp.

| Việc | Phối hợp với | Ghi chú |
|------|--------------|---------|
| **IP của Pi + Wi-Fi** (tên mạng + mật khẩu) để ESP32 nối vào | nhóm firmware | docs/20 để trống `<pi-ip>`, phải điền |
| **Lấy tín hiệu xe** (xi-nhan / số lùi / tốc độ) đưa vào `bsw/vehicle` | nhóm phần cứng + người có xe | **Rủi ro lớn nhất.** Hợp đồng đã chốt, nhưng cách đấu vào xe thì chưa. Thiếu thì hệ thống tự lùi về "theo dõi mọi vùng" |
| **Nguồn điện + màn hình 7" + loa + giá đỡ** (cơ khí) | nhóm phần cứng + mua sắm | Ngân sách ~20 triệu. BOM do nhóm phần cứng chốt. Đặt mua sớm vì hàng lâu về |
| **Watchdog phần cứng cho Pi** (ADR-0006) | nhóm firmware / dựng ảnh Pi | Làm ở giai đoạn G4 |

## 4. Với nhóm nghiên cứu / đánh giá (R)
Thống nhất 2 thứ:
1. **Kịch bản S1–S6** dưới dạng dữ liệu (vị trí vật, ngữ cảnh xe, kết quả mong đợi) → nạp vào sim.
2. **Số liệu chính** (tỉ lệ phát hiện / độ trễ / báo nhầm) phải đo từ **bench L4**,
   **không** lấy từ sim L3. Sim chỉ để kiểm tra hồi quy.

## 5. Checklist (đánh dấu khi xong)
- [ ] Đã đưa nhóm firmware: docs/20 + `tools/validate_message.py`.
- [ ] `sensor_id` của firmware khớp `config/sensors.example.json`.
- [ ] Đã báo IP của Pi + Wi-Fi cho nhóm firmware.
- [ ] Đã chốt cách lấy tín hiệu xe (hoặc đồng ý tạm bỏ).
- [ ] Đã đặt mua: Pi, ESP32 ×4, HC-SR04 ×8, màn hình 7", loa.
- [ ] Khi gắn cảm biến thật → cập nhật config cho khớp vị trí và `fire_group` thật.
- [ ] R: chốt kịch bản S1–S6 + thống nhất số liệu chính lấy từ L4.

---
*Tóm tắt: không cần thống nhất ngôn ngữ hay công cụ. Chỉ cần (1) firmware build theo docs/20,
(2) giữ `config/` khớp với phần cứng thật, (3) chốt 4 việc vật lý ở mục 3. Rủi ro lớn nhất:
lấy tín hiệu xe.*
