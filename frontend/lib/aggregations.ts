import type { Document } from "mongodb";
import type { Filters, SeverityBand } from "./types";
import { bandRange } from "./severity";

// Dev-only: cho phép tính cả record chưa enrich (xem bố cục khi data còn pending).
function includeNonDone(): boolean {
  return process.env.INCLUDE_NON_DONE === "1";
}

// Parse query params thành Filters. Tham số vắng → không ràng buộc.
export function parseFilters(sp: URLSearchParams): Filters {
  const from =
    sp.get("from") || process.env.NEXT_PUBLIC_DEFAULT_FROM || "2023-06-01";
  const to = sp.get("to") || process.env.NEXT_PUBLIC_DEFAULT_TO || "2026-06-30";
  const f: Filters = { from, to };

  const platform = sp.get("platform");
  if (platform) f.platform = platform;
  const severityBand = sp.get("severityBand");
  if (severityBand) f.severityBand = severityBand as SeverityBand;
  const productArea = sp.get("productArea");
  if (productArea) f.productArea = productArea;
  const topic = sp.get("topic");
  if (topic) f.topic = topic;
  const clusterId = sp.get("clusterId");
  if (clusterId) f.clusterId = clusterId;
  const keywordGroupId = sp.get("keywordGroupId");
  if (keywordGroupId) f.keywordGroupId = keywordGroupId;
  const intent = sp.get("intent");
  if (intent) f.intent = intent;
  const actionable = sp.get("actionable");
  if (actionable === "true" || actionable === "1") f.actionableOnly = true;

  return f;
}

// Build $match từ Filters. `withDate=false` để bỏ ràng buộc thời gian (vd đếm pending toàn cục).
export function buildMatch(
  f: Filters,
  opts: { withDate?: boolean; status?: boolean } = {},
): Document {
  const { withDate = true, status = true } = opts;
  const match: Document = {};

  if (status && !includeNonDone()) {
    match.status = "done";
  }

  if (withDate) {
    const range: Document = {};
    if (f.from) range.$gte = new Date(f.from);
    if (f.to) range.$lte = new Date(`${f.to}T23:59:59.999Z`);
    if (Object.keys(range).length) match.received_at = range;
  }

  if (f.platform) match.platform = f.platform;
  if (f.productArea) match.bi_product_area = f.productArea;
  if (f.topic) match.bi_topic = f.topic;
  // cluster_id / keyword_group_ids lưu dạng int trong Mongo → ép Number để $match khớp
  // (keyword_group_ids là mảng int → match value sẽ khớp document có phần tử bằng nó).
  if (f.clusterId != null) match.cluster_id = Number(f.clusterId);
  if (f.keywordGroupId != null) match.keyword_group_ids = Number(f.keywordGroupId);
  if (f.intent) match.bi_intent = f.intent;
  if (f.actionableOnly) match.bi_is_actionable = true;

  if (f.severityBand) {
    const { min, max } = bandRange(f.severityBand);
    match.bi_severity = { $gte: min, $lte: max };
  }

  return match;
}

// $switch tạo nhãn band từ bi_severity (dùng cho timeline stack & histogram).
export const SEVERITY_BAND_EXPR: Document = {
  $switch: {
    branches: [
      { case: { $lte: ["$bi_severity", 3] }, then: "low" },
      { case: { $lte: ["$bi_severity", 6] }, then: "medium" },
      { case: { $lte: ["$bi_severity", 8] }, then: "high" },
    ],
    default: "critical",
  },
};
