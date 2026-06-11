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
    const limit = Math.max(1, Math.min(50, Number(sp.get("limit")) || 15));
    const coll = await mentionsCollection();
    const match = buildMatch(f);
    if (!match.bi_topic) match.bi_topic = { $ne: null };
    // NOTE: group theo bi_topic thô để cross-filter khớp chính xác. Mức chuẩn hóa/gộp
    // ("khác", lowercase/trim) là open-question — chốt sau khi backfill xong, calibrate trên data thật.
    const rows = await coll
      .aggregate([
        { $match: match },
        {
          $group: {
            _id: "$bi_topic",
            count: { $sum: 1 },
            sevSum: { $sum: { $ifNull: ["$bi_severity", 0] } },
            sevCount: { $sum: { $cond: [{ $ne: ["$bi_severity", null] }, 1, 0] } },
          },
        },
        { $sort: { count: -1 } },
        { $limit: limit },
      ])
      .toArray();

    return rows.map((r) => ({
      key: String(r._id),
      count: r.count as number,
      avg_severity: r.sevCount > 0 ? Math.round((r.sevSum / r.sevCount) * 10) / 10 : 0,
    }));
  });
}
