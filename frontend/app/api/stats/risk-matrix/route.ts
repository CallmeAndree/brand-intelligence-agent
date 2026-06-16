import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch } from "@/lib/aggregations";
import { handle } from "@/lib/response";
import type { RiskMatrixItem } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Ma trận ưu tiên xử lý: mỗi bi_product_area → { volume, severity TB }.
export async function GET(req: NextRequest) {
  return handle<RiskMatrixItem[]>(async () => {
    const sp = req.nextUrl.searchParams;
    const f = parseFilters(sp);
    const coll = await mentionsCollection();
    const match = buildMatch(f);
    if (!match.bi_product_area) match.bi_product_area = { $ne: null };
    const rows = await coll
      .aggregate([
        { $match: match },
        {
          $group: {
            _id: "$bi_product_area",
            volume: { $sum: 1 },
            sev: { $avg: "$bi_severity" },
          },
        },
        { $sort: { volume: -1 } },
      ])
      .toArray();

    return rows.map((r) => ({
      key: String(r._id),
      volume: r.volume as number,
      sev: Math.round(((r.sev as number) ?? 0) * 10) / 10,
    }));
  });
}
