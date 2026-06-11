import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch, SEVERITY_BAND_EXPR } from "@/lib/aggregations";
import { handle } from "@/lib/response";
import { SEVERITY_BANDS } from "@/lib/severity";
import type { CountItem } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return handle<CountItem[]>(async () => {
    const f = parseFilters(req.nextUrl.searchParams);
    const coll = await mentionsCollection();
    const match = buildMatch(f);
    // chỉ tính record có bi_severity (giữ nguyên ràng buộc band nếu filter đang bật)
    if (!match.bi_severity) match.bi_severity = { $ne: null, $exists: true };
    const rows = await coll
      .aggregate([
        { $match: match },
        { $group: { _id: SEVERITY_BAND_EXPR, count: { $sum: 1 } } },
      ])
      .toArray();

    const counts = new Map(rows.map((r) => [String(r._id), r.count as number]));
    // Trả đủ 4 band theo thứ tự, fill 0.
    return SEVERITY_BANDS.map((b) => ({ key: b.band, count: counts.get(b.band) ?? 0 }));
  });
}
