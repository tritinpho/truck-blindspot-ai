// Scene config: the single-sourced zone map (config/zones.example.json, FR-03). Geometry is
// normalized top-view (0..1). We derive each zone's centroid once at load — icons render at the
// centroid (06 §6.2: the 8-zone model IS the spatial resolution). Swap the JSON to render a
// tractor-trailer or bus with no code change (06 §6.6).

import zonesRaw from "../../../config/zones.example.json";

export interface ZoneCfg {
  id: string;
  enabled: boolean;
  risk_weight: number;
  caution_m: number;
  danger_m: number;
  polygon_norm: number[][];
  centroid: [number, number];
}

export interface SceneConfig {
  vehicleProfile: string;
  truckOutline: number[][];
  truckCentroid: [number, number];
  zones: ZoneCfg[];
  defaults: { caution_m: number; danger_m: number };
}

interface RawZone {
  id: string;
  enabled?: boolean;
  risk_weight?: number;
  caution_m?: number;
  danger_m?: number;
  polygon_norm: number[][];
}
interface RawConfig {
  vehicle_profile?: string;
  truck_outline_norm: number[][];
  defaults?: { caution_m?: number; danger_m?: number };
  zones: RawZone[];
}

export function centroid(points: number[][]): [number, number] {
  const n = points.length || 1;
  const x = points.reduce((a, p) => a + p[0], 0) / n;
  const y = points.reduce((a, p) => a + p[1], 0) / n;
  return [x, y];
}

export function loadSceneConfig(): SceneConfig {
  const raw = zonesRaw as unknown as RawConfig;
  const d = raw.defaults ?? {};
  const dCaution = d.caution_m ?? 1.5;
  const dDanger = d.danger_m ?? 0.8;

  const zones: ZoneCfg[] = raw.zones.map((z) => ({
    id: z.id,
    enabled: z.enabled ?? true,
    risk_weight: z.risk_weight ?? 1.0,
    caution_m: z.caution_m ?? dCaution,
    danger_m: z.danger_m ?? dDanger,
    polygon_norm: z.polygon_norm,
    centroid: centroid(z.polygon_norm),
  }));

  return {
    vehicleProfile: raw.vehicle_profile ?? "unknown",
    truckOutline: raw.truck_outline_norm,
    truckCentroid: centroid(raw.truck_outline_norm),
    zones,
    defaults: { caution_m: dCaution, danger_m: dDanger },
  };
}
