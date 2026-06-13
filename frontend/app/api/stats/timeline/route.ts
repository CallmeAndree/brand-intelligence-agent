import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch } from "@/lib/aggregations";
import { handle } from "@/lib/response";
import type { TimelinePoint, TimelineBucket } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BUCKET_FORMAT: Record<TimelineBucket, string> = {
  day: "%Y-%m-%d",
  week: "%G-W%V",
  month: "%Y-%m",
};

export async function GET(req: NextRequest) {
  return handle<{ points: TimelinePoint[] }>(async () => {
    const sp = req.nextUrl.searchParams;
    const f = parseFilters(sp);
    const bucket = (sp.get("bucket") as TimelineBucket) || "month";
    const fmt = BUCKET_FORMAT[bucket] ?? BUCKET_FORMAT.month;

    const coll = await mentionsCollection();
    const match = buildMatch(f);
    if (!match.bi_severity) match.bi_severity = { $ne: null, $exists: true };

    const rows = await coll
      .aggregate([
        { $match: match },
        {
          $group: {
            _id: { $dateToString: { format: fmt, date: "$received_at" } },
            avg: { $avg: "$bi_severity" },
          },
        },
        { $sort: { _id: 1 } },
      ])
      .toArray();

    const points = rows.map((r) => ({
      date: String(r._id),
      avg: Math.round((Number(r.avg) || 0) * 10) / 10,
    }));

    return { points };
  });
}
