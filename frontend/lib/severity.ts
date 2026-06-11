import type { SeverityBand } from "./types";

// Band hóa bi_severity 1–10 (⚠️ thang 1–10, KHÔNG phải 1–5).
export const SEVERITY_BANDS: {
  band: SeverityBand;
  label: string;
  min: number;
  max: number;
  color: string;
}[] = [
  { band: "low", label: "Low (1–3)", min: 1, max: 3, color: "#c9c2b0" }, // xám/cream
  { band: "medium", label: "Medium (4–6)", min: 4, max: 6, color: "#e8b94a" }, // ochre
  { band: "high", label: "High (7–8)", min: 7, max: 8, color: "#ffb084" }, // peach
  { band: "critical", label: "Critical (9–10)", min: 9, max: 10, color: "#ef4444" }, // error đỏ
];

export const CRITICAL_MIN = 7; // KPI critical_count: severity >= 7

export function bandOf(severity: number | null | undefined): SeverityBand | null {
  if (severity == null) return null;
  for (const b of SEVERITY_BANDS) {
    if (severity >= b.min && severity <= b.max) return b.band;
  }
  return null;
}

export function bandColor(band: SeverityBand): string {
  return SEVERITY_BANDS.find((b) => b.band === band)?.color ?? "#c9c2b0";
}

export function bandRange(band: SeverityBand): { min: number; max: number } {
  const b = SEVERITY_BANDS.find((x) => x.band === band)!;
  return { min: b.min, max: b.max };
}

// Palette dùng cho phân loại platform/topic (6 feature colors + xoay vòng).
export const CATEGORICAL_PALETTE = [
  "#ff4d8b",
  "#1a3a3a",
  "#b8a4ed",
  "#ffb084",
  "#e8b94a",
  "#22c55e",
];
