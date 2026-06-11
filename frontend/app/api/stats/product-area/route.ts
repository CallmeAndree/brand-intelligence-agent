import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch } from "@/lib/aggregations";
import { handle } from "@/lib/response";
import type { CountItem } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return handle<CountItem[]>(async () => {
    const sp = req.nextUrl.searchParams;
    const f = parseFilters(sp);
    const limit = Math.max(1, Math.min(50, Number(sp.get("limit")) || 10));
    const coll = await mentionsCollection();
    const match = buildMatch(f);
    if (!match.bi_product_area) match.bi_product_area = { $ne: null };
    const rows = await coll
      .aggregate([
        { $match: match },
        { $group: { _id: "$bi_product_area", count: { $sum: 1 } } },
        { $sort: { count: -1 } },
        { $limit: limit },
      ])
      .toArray();

    return rows.map((r) => ({ key: String(r._id), count: r.count as number }));
  });
}
