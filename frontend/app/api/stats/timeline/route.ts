import { NextRequest } from "next/server";
import type { Document } from "mongodb";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch, SEVERITY_BAND_EXPR } from "@/lib/aggregations";
import { handle } from "@/lib/response";
import type { TimelinePoint, TimelineBucket, TimelineGroupBy } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BUCKET_FORMAT: Record<TimelineBucket, string> = {
  day: "%Y-%m-%d",
  week: "%G-W%V",
  month: "%Y-%m",
};

function seriesExpr(groupBy: TimelineGroupBy): Document {
  if (groupBy === "platform") return { $ifNull: ["$platform", "unknown"] };
  if (groupBy === "topic") return { $ifNull: ["$bi_topic", "unknown"] };
  return SEVERITY_BAND_EXPR; // severityBand (default)
}

export async function GET(req: NextRequest) {
  return handle<{ points: TimelinePoint[]; series: string[] }>(async () => {
    const sp = req.nextUrl.searchParams;
    const f = parseFilters(sp);
    const bucket = (sp.get("bucket") as TimelineBucket) || "month";
    const groupBy = (sp.get("groupBy") as TimelineGroupBy) || "severityBand";
    const fmt = BUCKET_FORMAT[bucket] ?? BUCKET_FORMAT.month;

    const coll = await mentionsCollection();
    const rows = await coll
      .aggregate([
        { $match: buildMatch(f) },
        {
          $group: {
            _id: {
              t: { $dateToString: { format: fmt, date: "$received_at" } },
              s: seriesExpr(groupBy),
            },
            count: { $sum: 1 },
          },
        },
        { $sort: { "_id.t": 1 } },
      ])
      .toArray();

    // Pivot ở Node: [{ date, <series>: count, ... }]
    const seriesSet = new Set<string>();
    const byDate = new Map<string, TimelinePoint>();
    for (const r of rows) {
      const date = r._id.t as string;
      const s = String(r._id.s ?? "unknown");
      seriesSet.add(s);
      if (!byDate.has(date)) byDate.set(date, { date });
      (byDate.get(date) as TimelinePoint)[s] = r.count;
    }
    const series = Array.from(seriesSet);
    const points = Array.from(byDate.values()).map((p) => {
      for (const s of series) if (p[s] == null) p[s] = 0;
      return p;
    });
    points.sort((a, b) => a.date.localeCompare(b.date));

    return { points, series };
  });
}
