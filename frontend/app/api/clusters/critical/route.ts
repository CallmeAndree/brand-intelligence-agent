import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch } from "@/lib/aggregations";
import { handle } from "@/lib/response";
import type { CriticalCluster, Trend } from "@/lib/types";
import type { Document } from "mongodb";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const CRITICAL_MIN = Number(process.env.CRITICAL_MIN) || 7;

// Group mentions theo cluster_id trong [from,to] (D1: KHÔNG đọc clusters lũy kế),
// lọc severity_max ≥ CRITICAL_MIN, trend = so count với kỳ liền trước cùng độ dài.
export async function GET(req: NextRequest) {
  return handle<CriticalCluster[]>(async () => {
    const sp = req.nextUrl.searchParams;
    // Critical list là OVERVIEW mọi cụm → bỏ các dim drill-down (clusterId/
    // keywordGroupId/topic) khỏi $match, nếu không khi user chọn 1 cụm thì
    // FilterProvider đẩy clusterId vào query và danh sách co lại còn đúng cụm đó.
    const f = { ...parseFilters(sp), clusterId: undefined, keywordGroupId: undefined, topic: undefined };
    const coll = await mentionsCollection();

    const groupStage: Document = {
      $group: {
        _id: "$cluster_id",
        label: { $first: "$cluster_label" },
        count: { $sum: 1 },
        severity_max: { $max: { $ifNull: ["$bi_severity", 0] } },
        sevSum: { $sum: { $ifNull: ["$bi_severity", 0] } },
        sevCount: { $sum: { $cond: [{ $ne: ["$bi_severity", null] }, 1, 0] } },
        last_seen: { $max: "$received_at" },
      },
    };
    const clusterFilter: Document = { cluster_id: { $nin: [null, -1] } };

    const curMatch = { ...buildMatch(f), ...clusterFilter };
    const curRows = await coll
      .aggregate([{ $match: curMatch }, groupStage])
      .toArray();

    // Kỳ liền trước cùng độ dài (cho trend).
    const fromMs = new Date(f.from).getTime();
    const toMs = new Date(`${f.to}T23:59:59.999Z`).getTime();
    const dur = Math.max(toMs - fromMs, 0);
    const prevFrom = new Date(fromMs - dur).toISOString().slice(0, 10);
    const prevTo = new Date(Math.max(fromMs - 1, 0)).toISOString().slice(0, 10);
    const prevMatch = {
      ...buildMatch({ ...f, from: prevFrom, to: prevTo }),
      ...clusterFilter,
    };
    const prevRows = await coll
      .aggregate([{ $match: prevMatch }, { $group: { _id: "$cluster_id", count: { $sum: 1 } } }])
      .toArray();
    const prevMap = new Map<number, number>(
      prevRows.map((r) => [r._id as number, r.count as number]),
    );

    const trendOf = (cur: number, prev: number): Trend => {
      if (prev === 0) return cur > 0 ? "up" : "flat";
      if (cur > prev * 1.1) return "up";
      if (cur < prev * 0.9) return "down";
      return "flat";
    };

    return curRows
      .filter((r) => (r.severity_max as number) >= CRITICAL_MIN && r._id != null)
      .map((r) => {
        const cluster_id = r._id as number;
        const count = r.count as number;
        return {
          cluster_id,
          label: String(r.label ?? `Cụm #${cluster_id}`),
          count,
          severity_max: r.severity_max as number,
          severity_avg:
            r.sevCount > 0 ? Math.round((r.sevSum / r.sevCount) * 10) / 10 : 0,
          last_seen: r.last_seen ? new Date(r.last_seen).toISOString() : null,
          trend: trendOf(count, prevMap.get(cluster_id) ?? 0),
        };
      })
      .sort((a, b) => b.severity_max - a.severity_max || b.count - a.count);
  });
}
