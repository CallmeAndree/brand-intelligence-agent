import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { handle } from "@/lib/response";
import type { ClusterDetail, Mention } from "@/lib/types";
import type { Document } from "mongodb";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Chi tiết một cụm: thông tin tổng hợp + mention thành viên (phân trang, sắp theo
// severity rồi recency). Đọc trực tiếp mentions (D1) — KHÔNG dùng clusters lũy kế.
export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  return handle<ClusterDetail>(async () => {
    const cluster_id = Number(params.id);
    const sp = req.nextUrl.searchParams;
    const skip = Math.max(0, Number(sp.get("skip")) || 0);
    const limit = Math.max(1, Math.min(100, Number(sp.get("limit")) || 20));
    const coll = await mentionsCollection();
    const match: Document = { cluster_id, status: "done" };

    const [agg] = await coll
      .aggregate([
        { $match: match },
        {
          $group: {
            _id: "$cluster_id",
            label: { $first: "$cluster_label" },
            count: { $sum: 1 },
            severity_max: { $max: "$bi_severity" },
            sevSum: { $sum: { $ifNull: ["$bi_severity", 0] } },
            sevCount: { $sum: { $cond: [{ $ne: ["$bi_severity", null] }, 1, 0] } },
          },
        },
      ])
      .toArray();

    const total = agg ? (agg.count as number) : 0;
    const docs = await coll
      .find(match)
      .sort({ bi_severity: -1, received_at: -1 })
      .skip(skip)
      .limit(limit)
      .toArray();

    return {
      cluster_id,
      label: agg ? String(agg.label ?? `Cụm #${cluster_id}`) : `Cụm #${cluster_id}`,
      count: total,
      severity_max: agg ? (agg.severity_max as number) : null,
      severity_avg:
        agg && agg.sevCount > 0
          ? Math.round((agg.sevSum / agg.sevCount) * 10) / 10
          : null,
      total,
      mentions: docs.map((d) => ({
        ...(d as unknown as Mention),
        _id: String(d._id),
        received_at: d.received_at ? new Date(d.received_at).toISOString() : null,
      })),
    };
  });
}
