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
  clusterId?: string;
  keywordGroupId?: string;
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

export type TimelineBucket = "day" | "week" | "month";

export interface TimelinePoint {
  date: string; // bucket label, vd "2026-01"
  avg: number;
}

export interface CountItem {
  key: string;
  count: number;
}

export interface TopicItem extends CountItem {
  avg_severity: number;
  cluster_id?: string | null;
  mode?: "cluster" | "raw";
}

export interface KeywordItem {
  label: string;
  weight: number;
  keyword_group_id?: string | null;
  mode?: "cluster" | "raw";
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

// ---- Chat (contract chung FE ↔ proxy/Runtime 2 — chatbot-frontend.md §2) ----
// Structured ngay từ slice sơ: slice này chỉ điền `text`; charts/citations/refs
// để optional cho slice sau (inline chart, issue-aware retrieval) — FE không đổi parser.
export interface ChatCitation {
  url: string;
  author: string;
  source?: string;
}

export interface ChatRef {
  issue_id?: string;
  episode_id?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  charts?: EChartSpec[];
  citations?: ChatCitation[];
  refs?: ChatRef[];
}

// ---- Monitor workspace (cụm critical + artifact AI) ----
export type Trend = "up" | "down" | "flat";

export interface CriticalCluster {
  cluster_id: number;
  label: string;
  count: number;
  severity_max: number;
  severity_avg: number;
  last_seen: string | null; // ISO
  trend: Trend;
}

export type ArtifactType =
  | "narrative"
  | "root_cause"
  | "response_strategy"
  | "brand_voice"
  | "seeding_comments";

export type ArtifactStatus = "draft" | "approved" | "discarded";

export interface ArtifactVariant {
  label: string;
  content_md: string;
}

export interface MonitorArtifact {
  _id: string;
  cluster_id: number;
  type: ArtifactType;
  status: ArtifactStatus;
  content_md: string;
  variants?: ArtifactVariant[] | null;
  model_meta: { model: string; prompt_file: string };
  source_mention_ids?: string[];
  created_at?: string;
}

export interface ClusterDetail {
  cluster_id: number;
  label: string;
  count: number;
  severity_max: number | null;
  severity_avg: number | null;
  mentions: Mention[];
  total: number;
}

// ---- Manual alert ----
export type EmailStatus = "sent" | "skipped" | "failed";

export interface AlertEmail {
  to?: string | null;
  subject?: string | null;
  status: EmailStatus;
  error?: string | null;
  sent_at?: string | null;
}

export interface Alert {
  _id: string;
  kind: string;
  cluster_id: number;
  department: string;
  severity_snapshot?: number | null;
  brief_md: string;
  email: AlertEmail;
  source_mention_ids?: string[];
  created_at?: string;
}

// ---- Response envelope (giống StandardResponse backend) ----
export interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  message?: string;
}
