import { NextRequest } from "next/server";
import { collectionByName } from "@/lib/mongo";
import { handle } from "@/lib/response";
import type { MonitorArtifact } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Đọc artifact đã gắn cụm (D2: read qua facade). Mặc định ẩn bản discarded.
export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  return handle<MonitorArtifact[]>(async () => {
    const cluster_id = Number(params.id);
    const includeDiscarded = req.nextUrl.searchParams.get("all") === "1";
    const coll = await collectionByName("monitor_artifacts");
    const filter: Record<string, unknown> = { cluster_id };
    if (!includeDiscarded) filter.status = { $ne: "discarded" };

    const docs = await coll
      .find(filter)
      .sort({ created_at: -1 })
      .limit(100)
      .toArray();

    return docs.map((d) => ({
      ...(d as unknown as MonitorArtifact),
      _id: String(d._id),
      created_at: d.created_at ? new Date(d.created_at).toISOString() : undefined,
    }));
  });
}
