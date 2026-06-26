# 12 — Traceability Matrix

Proves nothing in the proposal was dropped: every proposal section maps to requirements,
design, and tests. Useful for the examiners and for the final report.

## 12.1 Proposal content → design → tests

Proposal sections use the original numbering (Mục tiêu, Nội dung 1–6).

| Proposal item (VI) | Requirements | Design doc(s) | Tests |
|--------------------|--------------|---------------|-------|
| Mục tiêu — cảm biến đa vị trí, bộ xử lý, màn hình cabin | FR-01..07 | [03](03-architecture.md), [05](05-warning-logic.md), [06](06-hmi-design.md) | TC-S1..S6 |
| Nội dung 1 — Khảo sát điểm mù, tình huống nguy hiểm | FR-01, scenarios S1–S6 | [01](01-overview.md), [02](02-requirements.md) §2.3 | TC-S1..S6 |
| Nội dung 2 — Bố trí cảm biến, mã vị trí | FR-02, FR-03 | [`config/sensors.example.json`](../config/sensors.example.json), [ADR-0004](adr/ADR-0004-sensor-modality.md) | TC-F1 |
| Nội dung 3 — Nguyên lý xử lý tín hiệu, ánh xạ vị trí→vùng | FR-02, FR-04, FR-08, FR-09 | [04](04-message-protocol.md), [05](05-warning-logic.md) | TC-S2, TC-F2, TC-F3, L2 |
| Nội dung 4 — Giao diện màn hình cảnh báo (top-view, màu, âm thanh) | FR-05, FR-06, FR-07, FR-12 | [06](06-hmi-design.md), [`config/zones.example.json`](../config/zones.example.json) | TC-S5, L5 |
| Nội dung 5 — Mô hình mô phỏng / thử nghiệm | FR-13 | [08](08-simulation.md), [ADR-0005](adr/ADR-0005-sim-real-parity.md) | L3, L4 |
| Nội dung 6 — Đánh giá tính khả thi | FR-10, FR-14, NFR-01,08,09 | [11](11-evaluation-plan.md) | L1–L5, all TC |
| Phương pháp (khảo sát, phân tích hệ thống, thiết kế, mô phỏng, thử nghiệm, chuyên gia) | — | [01](01-overview.md), [03](03-architecture.md), [08](08-simulation.md), [11](11-evaluation-plan.md) §11.5 | L3–L5 |
| Sản phẩm dự kiến (sơ đồ, mô hình, infographic, quy trình) | FR-05, FR-13 | [03](03-architecture.md) diagrams, [06](06-hmi-design.md), [09](09-roadmap.md) | — |
| Tính mới — mô-đun hóa vị trí cảm biến + ánh xạ cảnh báo | FR-02, FR-03, FR-08 | [`config/`](../config/), [05](05-warning-logic.md) §5.4, [10](10-improvements.md) #4,#12 | TC-S2 |
| Hiệu quả / hướng phát triển (cấp sở, thương mại hóa, sáng chế) | — | [09](09-roadmap.md), [10](10-improvements.md), [13](13-privacy-ethics.md), [`../LICENSE`](../LICENSE) | — |

## 12.2 Requirements → design → tests (forward trace)

| Req | Design | Test |
|-----|--------|------|
| FR-01 monitor zones | [05](05-warning-logic.md) §5.1, [`config/zones`](../config/zones.example.json) | TC-S1..S6 |
| FR-02 sensor→zone by position code | [04](04-message-protocol.md) §4.3.1, [`config/sensors`](../config/sensors.example.json) | L2, TC-F1 |
| FR-03 reconfigurable, no code change | [`config/`](../config/), [ADR-0004](adr/ADR-0004-sensor-modality.md) | manual config swap test |
| FR-04 severity classification | [05](05-warning-logic.md) §5.2 | L2 |
| FR-05 top-view colored zones | [06](06-hmi-design.md) §6.1–6.2 | L5 |
| FR-06 object icons | [06](06-hmi-design.md) §6.2 | L5 |
| FR-07 escalating audio | [05](05-warning-logic.md) §5.5, [06](06-hmi-design.md) §6.3 | TC-S1,S4 |
| FR-08 context-aware | [05](05-warning-logic.md) §5.4 | TC-S2,S3,S4,S6 |
| FR-09 debounce/hysteresis | [05](05-warning-logic.md) §5.3 | TC-F2 |
| FR-10 event logging | [03](03-architecture.md) §3.8, [11](11-evaluation-plan.md) §11.6 | L3–L4 logs |
| FR-11 camera classification (phase 2) | [04](04-message-protocol.md) §4.3.2, [ADR-0004](adr/ADR-0004-sensor-modality.md) | TC-F3 |
| FR-12 settings/calibration | [06](06-hmi-design.md) §6.4 | L5 |
| FR-13 simulator on same contract | [08](08-simulation.md), [ADR-0005](adr/ADR-0005-sim-real-parity.md) | L3 |
| FR-14 sensor fault → UNKNOWN | [05](05-warning-logic.md) §5.2, [04](04-message-protocol.md) §4.3.4 | TC-F1 |
| FR-15 system liveness | [06](06-hmi-design.md) §6.5, [ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md) | TC-F4 |
| NFR-01 latency (danger/boundary path) | [03](03-architecture.md) §3.5, [ADR-0007](adr/ADR-0007-sensor-firing-schedule.md) | TC latency measurement |
| NFR-02 refresh (per modality) | [06](06-hmi-design.md) §6.5, [ADR-0007](adr/ADR-0007-sensor-firing-schedule.md) | bench timing, TC-F5 |
| NFR-03 auto-restart | [03](03-architecture.md) §3.6 (systemd) | crash-recovery test |
| NFR-04 fail-safe | [05](05-warning-logic.md) §5.2 | TC-F1 |
| NFR-05 cost | [07](07-tech-stack.md) §7.3 | BOM review |
| NFR-06 portability | [ADR-0001](adr/ADR-0001-edge-compute-platform.md), [ADR-0003](adr/ADR-0003-hmi-stack.md) | run on Pi + laptop |
| NFR-07 configurability | [`config/`](../config/) | config swap test |
| NFR-08 glanceability | [06](06-hmi-design.md) | L5 glance-test |
| NFR-09 alert quality | [05](05-warning-logic.md) §5.8 | threshold sweep |
| NFR-10 maintainability | [ADR-0002](adr/ADR-0002-message-bus.md) | — |
| NFR-11 observability | [04](04-message-protocol.md), [06](06-hmi-design.md) §6.4 | diagnostics view |
| NFR-12 startup state | [06](06-hmi-design.md) §6.5, [ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md) | L4 boot test |

## 12.3 Coverage check

Every Nội dung (1–6), the Mục tiêu, the stated Tính mới, and all Must requirements trace to
at least one design doc and one test. Open items are tracked in [`09-roadmap.md`](09-roadmap.md)
milestones and [`10-improvements.md`](10-improvements.md).
