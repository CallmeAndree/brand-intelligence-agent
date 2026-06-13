import { NextRequest } from "next/server";
import { collectionByName } from "@/lib/mongo";
import { handle } from "@/lib/response";
import type { Alert } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Đọc lịch sử alert qua facade (D2). Lọc theo cluster_id nếu truyền.
export async function GET(req: NextRequest) {
  return handle<Alert[]>(async () => {
    const sp = req.nextUrl.searchParams;
    const limit = Math.max(1, Math.min(200, Number(sp.get("limit")) || 50));
    const clusterId = sp.get("clusterId");
    const coll = await collectionByName("alerts");
    const filter: Record<string, unknown> = {};
    if (clusterId) filter.cluster_id = Number(clusterId);

    const docs = await coll
      .find(filter)
      .sort({ created_at: -1 })
      .limit(limit)
      .toArray();

    return docs.map((d) => ({
      ...(d as unknown as Alert),
      _id: String(d._id),
      created_at: d.created_at ? new Date(d.created_at).toISOString() : undefined,
    }));
  });
}
