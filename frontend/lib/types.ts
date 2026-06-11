// Mirror các trường mentions từ backend (app/modules/ingestion/domain/models.py).

export type MentionStatus = "pending" | "done" | "failed";

export interface Mention {
  _id: string;
  mention: string;
  subject?: string | null;
  source?: string | null;
  platform?: string | null;
  author?: string | null;
  url?: string | null;
  received_at?: string | null; // ISO string sau khi serialize
  kompa_analysis?: string | null;
  has_ai_analysis?: boolean | null;
  status: MentionStatus;
  bi_topic?: string | null;
  bi_product_area?: string | null;
  bi_severity?: number | null; // 1–10
  bi_intent?: string | null;
  bi_is_actionable?: boolean | null;
  bi_summary_vi?: string | null;
}

// ---- Filter state chung (coordinated views) ----
export type SeverityBand = "low" | "medium" | "high" | "critical";

export interface Filters {
  from: string; // ISO date
  to: string; // ISO date
  platform?: string;
  severityBand?: SeverityBand;
  productArea?: string;
  topic?: string;
  intent?: string;
  actionableOnly?: boolean;
}

// ---- Shapes trả về từ API ----
export interface KpiStats {
  total: number;
  actionable_pct: number;
  avg_severity: number;
  critical_count: number;
  pending_count: number;
}

export type TimelineGroupBy = "severityBand" | "platform" | "topic";
export type TimelineBucket = "day" | "week" | "month";

export interface TimelinePoint {
  date: string; // bucket label, vd "2026-01"
  [seriesKey: string]: string | number;
}

export interface CountItem {
  key: string;
  count: number;
}

export interface TopicItem extends CountItem {
  avg_severity: number;
}

export interface MentionsPage {
  data: Mention[];
  total: number;
}

// ---- Chart wrapper ----
export interface EChartSpec {
  title?: string;
  option: Record<string, unknown>;
}

// ---- Response envelope (giống StandardResponse backend) ----
export interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  message?: string;
}
