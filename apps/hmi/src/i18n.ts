// Minimal VI/EN strings (FR-12 language toggle). Default Vietnamese — the project's context.
// Zone IDs stay canonical (FRONT, RIGHT, …) on the wire; only their DISPLAY name is localized.

import type { Lang, ObjectClass } from "./types";

type Dict = Record<string, string>;

const VI: Dict = {
  title: "BSW",
  warming: "ĐANG KHỞI ĐỘNG",
  warming_sub: "chưa giám sát — chờ dữ liệu vùng",
  signal_lost: "MẤT TÍN HIỆU",
  signal_lost_sub: "hệ thống không phản hồi",
  all_clear: "An toàn",
  live: "trực tiếp",
  // banner / units
  unit_m: "m",
  // status bar
  mute: "Tắt tiếng",
  unmute: "Bật tiếng",
  sound_hint: "Chạm để bật âm thanh",
  settings: "Cài đặt",
  diagnostics: "Chẩn đoán",
  back: "Quay lại",
  // settings
  thresholds: "Ngưỡng cảnh báo",
  caution: "Chú ý",
  danger: "Nguy hiểm",
  volume: "Âm lượng",
  language: "Ngôn ngữ",
  enabled: "Bật vùng",
  reset: "Đặt lại",
  zone: "Vùng",
  // diagnostics
  sensor: "Cảm biến",
  severity: "Mức",
  range: "Khoảng cách",
  age: "Tuổi (ms)",
  health: "Tình trạng",
  present: "Có vật",
  rate: "Tần suất",
  no_sensors: "Chưa có dữ liệu cảm biến thô (bsw/sensor/#)",
  msg_per_s: "tin/giây",
};

const EN: Dict = {
  title: "BSW",
  warming: "WARMING UP",
  warming_sub: "not yet monitoring — waiting for zone data",
  signal_lost: "SIGNAL LOST",
  signal_lost_sub: "system not responding",
  all_clear: "All clear",
  live: "live",
  unit_m: "m",
  mute: "Mute",
  unmute: "Unmute",
  sound_hint: "Tap to enable sound",
  settings: "Settings",
  diagnostics: "Diagnostics",
  back: "Back",
  thresholds: "Alert thresholds",
  caution: "Caution",
  danger: "Danger",
  volume: "Volume",
  language: "Language",
  enabled: "Zone on",
  reset: "Reset",
  zone: "Zone",
  sensor: "Sensor",
  severity: "Severity",
  range: "Range",
  age: "Age (ms)",
  health: "Health",
  present: "Present",
  rate: "Rate",
  no_sensors: "No raw sensor data yet (bsw/sensor/#)",
  msg_per_s: "msg/s",
};

const ZONE_VI: Dict = {
  FRONT: "TRƯỚC", FRONT_LEFT: "TRƯỚC-TRÁI", FRONT_RIGHT: "TRƯỚC-PHẢI",
  LEFT: "TRÁI", RIGHT: "PHẢI",
  REAR_LEFT: "SAU-TRÁI", REAR_RIGHT: "SAU-PHẢI", REAR: "SAU",
};
const ZONE_EN: Dict = {
  FRONT: "FRONT", FRONT_LEFT: "FRONT-LEFT", FRONT_RIGHT: "FRONT-RIGHT",
  LEFT: "LEFT", RIGHT: "RIGHT",
  REAR_LEFT: "REAR-LEFT", REAR_RIGHT: "REAR-RIGHT", REAR: "REAR",
};

const CLASS_VI: Dict = {
  pedestrian: "người đi bộ", cyclist: "xe đạp", motorbike: "xe máy",
  vehicle: "ô tô", unknown: "vật thể",
};
const CLASS_EN: Dict = {
  pedestrian: "pedestrian", cyclist: "cyclist", motorbike: "motorbike",
  vehicle: "vehicle", unknown: "object",
};

let lang: Lang = "vi";

export function setLang(l: Lang): void { lang = l; }
export function getLang(): Lang { return lang; }

export function t(key: string): string {
  return (lang === "vi" ? VI : EN)[key] ?? key;
}

export function zoneName(id: string): string {
  return (lang === "vi" ? ZONE_VI : ZONE_EN)[id] ?? id;
}

export function className(c: ObjectClass): string {
  if (!c) return "";
  return (lang === "vi" ? CLASS_VI : CLASS_EN)[c] ?? "";
}
