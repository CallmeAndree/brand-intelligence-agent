import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch } from "@/lib/aggregations";
import { handle } from "@/lib/response";
import type { KeywordItem } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return handle<KeywordItem[]>(async () => {
    const sp = req.nextUrl.searchParams;
    const f = parseFilters(sp);
    const limit = Math.max(1, Math.min(50, Number(sp.get("limit")) || 40));
    const coll = await mentionsCollection();
    const baseMatch = buildMatch(f);

    // Nhãn cụm keyword nằm ở collection `keyword_groups`; mention chỉ có
    // `keyword_group_ids: int[]`. Detect "đã cluster" = có mention mang group ids.
    const clusteredCount = await coll.countDocuments({
      ...baseMatch,
      keyword_group_ids: { $exists: true, $ne: [] },
    });
    const useClusters = clusteredCount > 0;

    const rows = await coll
      .aggregate(
        useClusters
          ? [
              {
                $match: {
                  ...baseMatch,
                  keyword_group_ids: { $exists: true, $ne: [] },
                },
              },
              { $unwind: "$keyword_group_ids" },
              { $match: { keyword_group_ids: { $ne: -1 } } }, // bỏ noise group
              { $group: { _id: "$keyword_group_ids", weight: { $sum: 1 } } },
              { $sort: { weight: -1 } },
              { $limit: limit },
              {
                $lookup: {
                  from: "keyword_groups",
                  localField: "_id",
                  foreignField: "_id",
                  as: "g",
                },
              },
              {
                $project: {
                  weight: 1,
                  label: {
                    $ifNull: [
                      { $arrayElemAt: ["$g.label", 0] },
                      { $concat: ["#", { $toString: "$_id" }] },
                    ],
                  },
                },
              },
            ]
          : [
              {
                $match: {
                  ...baseMatch,
                  bi_keywords: { $exists: true, $ne: [] },
                },
              },
              { $unwind: "$bi_keywords" },
              { $group: { _id: "$bi_keywords", weight: { $sum: 1 } } },
              { $sort: { weight: -1 } },
              { $limit: limit },
            ],
      )
      .toArray();

    return rows.map((r) => ({
      label: String(useClusters ? r.label : r._id),
      weight: r.weight as number,
      keyword_group_id: useClusters && r._id != null ? String(r._id) : null,
      mode: useClusters ? "cluster" : "raw",
    }));
  });
}
