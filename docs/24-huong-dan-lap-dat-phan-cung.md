# 24 — Hướng dẫn lắp đặt phần cứng & chạy thử (W track)

**Cho ai.** Người làm phần cứng / firmware (nhóm W).
**Phạm vi.** Phần vật lý: linh kiện, gắn cảm biến, nguồn, mạng, màn hình, chạy thử.
Hợp đồng firmware (định dạng tin nhắn) nằm ở [`20-firmware-contract-checklist.md`](20-firmware-contract-checklist.md) —
**giữ nguyên, doc này không lặp lại**. Phần phối hợp giữa các nhóm xem
[`23-ban-giao-tich-hop.md`](23-ban-giao-tich-hop.md).

## 1. Linh kiện (BOM)
Tham khảo [`07-tech-stack.md`](07-tech-stack.md) §7.3. Cốt lõi:

| Linh kiện | SL |
|-----------|:--:|
| Raspberry Pi 4 + thẻ nhớ + nguồn | 1 |
| ESP32 | 4 |
| Cảm biến siêu âm HC-SR04 | 8 |
| Màn hình 7" HDMI/cảm ứng | 1 |
| Loa/buzzer + mạch khuếch đại | 1 |
| Dây, giá đỡ, mô hình xe… | — |

Ngân sách ~20 triệu. **BOM cuối do nhóm phần cứng chốt. Đặt mua sớm vì hàng lâu về.**

## 2. Gắn cảm biến đúng vị trí
8 cảm biến siêu âm, mỗi cái một vị trí và một `sensor_id` cố định
(theo [`../config/sensors.example.json`](../config/sensors.example.json)):

| `sensor_id` | Vị trí gắn | `fire_group` |
|-------------|-----------|:------------:|
| `front_center` | giữa cản trước | 0 |
| `left_mid` | giữa hông trái | 0 |
| `right_mid` | giữa hông phải **(nguy hiểm nhất)** | 0 |
| `rear_center` | giữa cản sau | 0 |
| `front_left` | góc trước trái | 1 |
| `front_right` | góc trước phải | 1 |
| `rear_left` | góc sau trái | 1 |
| `rear_right` | góc sau phải | 1 |

- `right_mid` (hông phải) là vùng nguy hiểm nhất → gắn chắc, đúng hướng.
- Gắn xong mà khác bảng → **sửa config trên Pi, không sửa firmware**.

## 3. Nhóm bắn (`fire_group`) — tránh nhiễu chéo
8 cảm biến bắn cùng lúc sẽ nghe nhầm sóng của nhau. Cách tránh: chia 2 nhóm, bắn xen kẽ.
- Group 0 = 4 cái giữa/hông; Group 1 = 4 góc.
- Mỗi cảm biến lấy mẫu ~5 Hz. Chi tiết: [ADR-0007](adr/ADR-0007-sensor-firing-schedule.md) +
  [`20 §20.3`](20-firmware-contract-checklist.md).

## 4. Cấp nguồn (cần chốt)
- Pi 4: 5V / 3A.
- ESP32 + HC-SR04: 5V.
- **Bản mẫu / mô hình:** có thể dùng nguồn USB hoặc pin sạc dự phòng.
- **Lên xe thật (pilot):** xe 24V → cần bộ hạ áp DC-DC + cầu chì. Đây là việc của nhóm phần cứng.

## 5. Mạng (Wi-Fi + broker)
- ESP32 nối Wi-Fi → `mqtt://<ip-cua-pi>:1883`.
- **Cần xin phần mềm/Pi:** tên Wi-Fi + mật khẩu, và **IP tĩnh của Pi**.
- Dự phòng: nếu Wi-Fi nhiễu trong thùng kim loại → đi dây UART/RS-485
  ([ADR-0002](adr/ADR-0002-message-bus.md)).

## 6. Màn hình + loa
- Màn 7" cắm HDMI vào Pi; phần mềm chạy ở chế độ Chromium kiosk (phần mềm lo).
- Loa/buzzer cắm cổng âm thanh của Pi.

## 7. Tín hiệu xe (chỉ khi lên xe thật)
- Xi-nhan / số / tốc độ → đưa vào `bsw/vehicle` qua GPIO hoặc OBD-II.
- **Bản mẫu / bench:** sim cấp sẵn các tín hiệu này, **chưa cần đấu vào xe**.
- Thiếu tín hiệu thì hệ thống tự lùi về "theo dõi mọi vùng" — vẫn chạy được.
- **Đây là rủi ro lớn nhất khi lên xe thật → bàn sớm.**

## 8. Watchdog cho Pi (giai đoạn G4)
Bật hardware watchdog để nếu Pi treo thì tự khởi động lại
([ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md)).

## 9. Chạy thử nghiệm thu (mục tiêu G4)
Theo [`20 §20.9`](20-firmware-contract-checklist.md):
1. Bật broker + fusion + HMI (`docker compose up`).
2. Cắm cảm biến, trỏ ESP32 về IP của Pi.
3. Đưa vật vào ~0.8 m ở hông phải → HMI tô đỏ vùng RIGHT, kêu bíp.
4. Rút cảm biến → trong ~0.7 s vùng đó thành **UNKNOWN** + một tiếng chuông (không bao giờ "xanh giả").

**Đạt bước 1–4 = xong G4.** Lúc này phần cứng thật và sim chạy giống hệt nhau.

## 10. Checklist (đánh dấu khi xong)
- [ ] Đủ linh kiện (mục 1).
- [ ] Gắn 8 cảm biến đúng vị trí + `sensor_id` (mục 2).
- [ ] `fire_group` đúng, bắn xen kẽ (mục 3).
- [ ] Nguồn ổn định cho Pi + ESP32 (mục 4).
- [ ] ESP32 nối được broker của Pi (mục 5).
- [ ] Màn hình + loa chạy (mục 6).
- [ ] (Xe thật) chốt cách lấy tín hiệu xe (mục 7).
- [ ] Bật watchdog Pi (mục 8).
- [ ] Chạy thử nghiệm thu đạt (mục 9).
