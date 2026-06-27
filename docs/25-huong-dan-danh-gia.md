# 25 — Hướng dẫn đánh giá & chạy kịch bản (nhóm R)

**Cho ai.** Nhóm nghiên cứu / đánh giá (R: thầy hướng dẫn + sinh viên).
**Mục đích.** Cách chạy kịch bản, lấy số liệu, và đánh giá người dùng cho báo cáo (Nội dung 6).
Kế hoạch đầy đủ ở [`11-evaluation-plan.md`](11-evaluation-plan.md) (tiếng Anh); doc này tóm tắt phần việc của R.

## 1. Năm mức kiểm thử
| Mức | Kiểm gì | Cần phần cứng? |
|-----|---------|:--------------:|
| L1 | Tin nhắn đúng định dạng | Không |
| L2 | Logic tính mức nguy hiểm | Không |
| L3 | Kịch bản S1–S6 chạy thông toàn tuyến (bằng sim) | Không |
| L4 | Phần cứng thật trên mô hình xe (ESP32 + siêu âm) | **Có** |
| L5 | Tài xế + chuyên gia đánh giá màn hình | Người thật |

L1–L3 chạy tự động, không cần phần cứng (nhờ sim/real parity).

## 2. Nguyên tắc quan trọng nhất ⚠️
**Số liệu "đinh" của báo cáo — tỉ lệ phát hiện, độ trễ, tỉ lệ báo nhầm — phải đo từ L4 (phần cứng
thật), KHÔNG lấy từ sim L3.** Lý do: sim tự suy ra "phát hiện" từ hình học vùng → lấy số của sim là
"tự chấm điểm mình". Sim L3 chỉ dùng để: kiểm tra logic đúng + chống hồi quy (lỡ sửa code làm hỏng
thì test báo).

| Số liệu | Mục tiêu | Lấy từ |
|---------|----------|--------|
| Tỉ lệ phát hiện | ≥ 95% | **L4** |
| Độ trễ (vùng nguy hiểm) | ≤ 200 ms | **L4** |
| Tỉ lệ báo nhầm | đủ thấp để tài xế không tắt máy | **L4** |
| Thời gian liếc nhìn gọi tên vùng | ≤ 1 s (≥ 95% số lần) | **L5** |
| Nhấp nháy (flicker) | ≈ 0 | L3 (đã đạt) |
| Lỗi cảm biến hiện UNKNOWN, không "xanh giả" | 100% | L3 (đã đạt) |

## 3. Kịch bản S1–S6 + ca lỗi
| Mã | Tình huống | Kết quả mong đợi |
|----|-----------|------------------|
| S1 | Xe chớm chạy, xe máy ở trước-phải | FRONT_RIGHT → DANGER, bíp nhanh |
| S2 | Ôm cua phải, xe máy sát hông phải | RIGHT → DANGER, banner = RIGHT |
| S3 | Chuyển làn trái | vùng trái → CAUTION/DANGER khi lại gần |
| S4 | Lùi xe, pallet phía sau | REAR → DANGER, kêu liên tục |
| S5 | Bò trong phố đông, 3+ vùng có vật | hiện hết; báo theo vùng nguy hiểm nhất; không loạn |
| S6 | Đỗ sát tường, số P | vùng trái hiện vàng, **tắt âm** (không làm phiền) |
| F1 | Rút cảm biến | vùng đó → UNKNOWN + 1 tiếng chuông |
| F2 | Vật rung quanh ngưỡng | debounce giữ, gần như không nhấp nháy |
| F3 | Người đi bộ vs ô tô cùng khoảng cách | người đi bộ báo sớm hơn (camera, phase-2) |
| F4 | Treo máy / tắt fusion | toàn màn → UNKNOWN + "SIGNAL LOST" |
| F5 | 8 cảm biến bắn 2 nhóm | mỗi cái ~5 Hz, không nhiễu chéo |

## 4. Chạy để lấy số liệu (trên laptop, cần Python)
```bash
pip install -r tests/requirements.txt

# chạy toàn bộ test (bằng chứng L1–L3):
pytest -q tests/ services/fusion-engine/tests

# tạo toàn bộ số liệu sim ra file Markdown:
python tools/eval_report.py

# xem một kịch bản (vd S2):
python tools/scenario_runner.py S2

# độ trễ ước lượng (sim):
python tools/scenario_runner.py --latency

# điểm vận hành (độ nhạy vs báo nhầm):
python tools/threshold_sweep.py
```
Chạy lại cho **số y hệt** mỗi lần (không phụ thuộc đồng hồ hay phần cứng) → số liệu trong báo cáo
lặp lại được, không phải "kể chuyện".

## 5. Đánh giá người dùng (L5)
- **Người tham gia:** ≥ 5 tài xế xe tải + ≥ 2 chuyên gia (an toàn giao thông / ô tô).
- **Cách làm:** cho ngồi trước màn hình chạy các kịch bản; mỗi kịch bản đo:
  - thời gian để gọi đúng tên vùng đang báo (mục tiêu ≤ 1 s),
  - gọi đúng hay sai,
  - rồi điền bảng hỏi Likert (rõ ràng, tin tưởng, mức khó chịu vì báo nhầm, có muốn dùng tiếp không).
- **Kết quả:** phân bố thời gian liếc nhìn, % đúng, ý kiến → đề xuất cải tiến màn hình.

## 6. Việc nhóm R phụ trách
- Chốt kịch bản S1–S6 thành **dữ liệu** (vị trí vật, ngữ cảnh xe, kết quả mong đợi) → nạp vào sim.
- Tuyển ≥ 5 tài xế + ≥ 2 chuyên gia; chuẩn bị bài test liếc nhìn + bảng Likert.
- Giữ khung báo cáo; **bắt buộc** số liệu chính lấy từ L4, không phải L3.

## 7. L4 + L5 còn phải đo (chưa làm được vì cần phần cứng / người thật)
- **L4:** tỉ lệ phát hiện thật, độ trễ thật (đo trên một đồng hồ), tỉ lệ báo nhầm thật, Hz thật,
  thời gian phục hồi sau treo máy.
- **L5:** thời gian liếc nhìn, độ đúng, điểm Likert.
- Danh sách đầy đủ: [`21-evaluation-report-inputs.md`](21-evaluation-report-inputs.md) §21.10.
