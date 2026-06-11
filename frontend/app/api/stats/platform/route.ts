import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch } from "@/lib/aggregations";
import { handle } from "@/lib/response";
import type { CountItem } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return handle<CountItem[]>(async () => {
    const f = parseFilters(req.nextUrl.searchParams);
    const coll = await mentionsCollection();
    const rows = await coll
      .aggregate([
        { $match: buildMatch(f) },
        // fallback: nếu platform null → dùng source
        {
          $group: {
            _id: { $ifNull: ["$platform", { $ifNull: ["$source", "unknown"] }] },
            count: { $sum: 1 },
          },
        },
        { $sort: { count: -1 } },
      ])
      .toArray();

    return rows.map((r) => ({ key: String(r._id), count: r.count as number }));
  });
}
