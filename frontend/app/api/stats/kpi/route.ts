import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch } from "@/lib/aggregations";
import { CRITICAL_MIN } from "@/lib/severity";
import { handle } from "@/lib/response";
import type { KpiStats } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return handle<KpiStats>(async () => {
    const f = parseFilters(req.nextUrl.searchParams);
    const coll = await mentionsCollection();

    const [row] = await coll
      .aggregate([
        { $match: buildMatch(f) },
        {
          $group: {
            _id: null,
            total: { $sum: 1 },
            actionable: {
              $sum: { $cond: [{ $eq: ["$bi_is_actionable", true] }, 1, 0] },
            },
            sevSum: { $sum: { $ifNull: ["$bi_severity", 0] } },
            sevCount: {
              $sum: { $cond: [{ $ne: ["$bi_severity", null] }, 1, 0] },
            },
            critical: {
              $sum: { $cond: [{ $gte: ["$bi_severity", CRITICAL_MIN] }, 1, 0] },
            },
          },
        },
      ])
      .toArray();

    // pending_count: record status=pending trong khoảng filter (báo tiến độ enrich).
    const pendingMatch = buildMatch(f, { status: false });
    pendingMatch.status = "pending";
    const pending_count = await coll.countDocuments(pendingMatch);

    const total = row?.total ?? 0;
    const sevCount = row?.sevCount ?? 0;
    return {
      total,
      actionable_pct: total > 0 ? Math.round((row.actionable / total) * 1000) / 10 : 0,
      avg_severity: sevCount > 0 ? Math.round((row.sevSum / sevCount) * 10) / 10 : 0,
      critical_count: row?.critical ?? 0,
      pending_count,
    };
  });
}
