import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch } from "@/lib/aggregations";
import { handle } from "@/lib/response";
import type { TopicItem } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return handle<TopicItem[]>(async () => {
    const sp = req.nextUrl.searchParams;
    const f = parseFilters(sp);
    const limit = Math.max(1, Math.min(50, Number(sp.get("limit")) || 10));
    const coll = await mentionsCollection();
    const baseMatch = buildMatch(f);

    const clusteredCount = await coll.countDocuments({
      ...baseMatch,
      cluster_label: { $nin: [null, ""] },
    });
    const useClusters = clusteredCount > 0;

    const match = { ...baseMatch };
    if (useClusters) {
      match.cluster_label = { $nin: [null, ""] };
      if (match.cluster_id == null) match.cluster_id = { $ne: -1 }; // bỏ cụm noise (giữ filter clusterId nếu có)
    } else if (!match.bi_topic) {
      match.bi_topic = { $ne: null };
    }

    const rows = await coll
      .aggregate([
        { $match: match },
        {
          $group: {
            _id: useClusters
              ? { label: "$cluster_label", cluster_id: "$cluster_id" }
              : { label: "$bi_topic", cluster_id: null },
            count: { $sum: 1 },
            sevSum: { $sum: { $ifNull: ["$bi_severity", 0] } },
            sevCount: {
              $sum: { $cond: [{ $ne: ["$bi_severity", null] }, 1, 0] },
            },
          },
        },
        { $sort: { count: -1 } },
        { $limit: limit },
      ])
      .toArray();

    return rows.map((r) => ({
      key: String(r._id.label),
      count: r.count as number,
      avg_severity:
        r.sevCount > 0 ? Math.round((r.sevSum / r.sevCount) * 10) / 10 : 0,
      cluster_id: r._id.cluster_id == null ? null : String(r._id.cluster_id),
      mode: useClusters ? "cluster" : "raw",
    }));
  });
}
