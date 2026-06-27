# 26 — Firmware ESP32: Bắt đầu nhanh (nhóm W)

Doc này chỉ để **định hướng nhanh**. Spec đầy đủ + checklist nằm ở
[`20-firmware-contract-checklist.md`](20-firmware-contract-checklist.md) (tiếng Anh, đã đóng băng) —
đọc doc 20 để làm, đọc doc này để hiểu nhanh việc. Lắp đặt phần cứng xem
[`24-huong-dan-lap-dat-phan-cung.md`](24-huong-dan-lap-dat-phan-cung.md).

## Bạn làm gì
- Bạn chỉ làm **một hộp**: ESP32 + cảm biến siêu âm.
- Đọc khoảng cách / có vật hay không → gửi **một tin JSON** lên `bsw/sensor/{sensor_id}` qua MQTT.
- Bạn **không** biết "zone", ngưỡng, hay mức nguy hiểm — Pi lo hết. Bạn chỉ gửi số đo thô.

## Tin nhắn duy nhất phải gửi
Lên topic `bsw/sensor/{sensor_id}` (xem đủ ở [`20 §20.1`](20-firmware-contract-checklist.md)):
```json
{ "schema": "bsw.sensor_reading/1", "sensor_id": "right_mid", "ts": 142037,
  "ts_kind": "monotonic_ms", "modality": "ultrasonic",
  "present": true, "range_m": 0.82, "health": "ok" }
```
Đổi khoảng cách HC-SR04 ra mét: `range_m = echo_us / 5800.0`.

## 5 điều DỄ SAI (nhớ kỹ)
1. `present=false` ⇒ `range_m` phải là **null** — không phải `0.0`, không bỏ trống.
2. `ts_kind` = **"monotonic_ms"** — ESP32 không có đồng hồ thật, dùng `millis()`.
3. `sensor_id` phải **trùng** nhánh cuối của topic và phải có trong `config/sensors.example.json`.
4. QoS **0**, **không** retain cho luồng cảm biến.
5. Đọc cảm biến lỗi → gửi `health:"fault"`, `present:false`, `range_m:null`.
   **Đừng im lặng, đừng báo "sạch" giả.**

## Tự kiểm trước khi tích hợp
```bash
pip install jsonschema
python tools/validate_message.py my_sample.json --strict
```
So tin của bạn với mẫu chuẩn ở `tests/fixtures/firmware/`.

## Các bước
1. Đọc kỹ [`docs/20`](20-firmware-contract-checklist.md).
2. Code theo mẫu [`../sim/geometry.py`](../sim/geometry.py) (hàm `_reading`) — phân vân field nào thì làm giống nó.
3. Tự kiểm bằng `validate_message.py`.
4. Lắp đặt phần cứng theo [`docs/24`](24-huong-dan-lap-dat-phan-cung.md).
5. Chạy thử nghiệm thu [`20 §20.9`](20-firmware-contract-checklist.md) → xong G4.
