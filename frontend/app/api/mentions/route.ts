import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch } from "@/lib/aggregations";
import { handle } from "@/lib/response";
import type { MentionsPage, Mention } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PROJECTION = {
  mention: 1,
  bi_summary_vi: 1,
  bi_severity: 1,
  bi_intent: 1,
  bi_product_area: 1,
  bi_topic: 1,
  platform: 1,
  source: 1,
  author: 1,
  url: 1,
  received_at: 1,
  status: 1,
};

export async function GET(req: NextRequest) {
  return handle<MentionsPage>(async () => {
    const sp = req.nextUrl.searchParams;
    const f = parseFilters(sp);
    const limit = Math.max(1, Math.min(200, Number(sp.get("limit")) || 50));
    const skip = Math.max(0, Number(sp.get("skip")) || 0);

    const coll = await mentionsCollection();
    const match = buildMatch(f);

    const [data, total] = await Promise.all([
      coll
        .find(match, { projection: PROJECTION })
        .sort({ received_at: -1 })
        .skip(skip)
        .limit(limit)
        .toArray(),
      coll.countDocuments(match),
    ]);

    // _id → string; received_at → ISO string
    const items = data.map((d) => ({
      ...d,
      _id: String(d._id),
      received_at: d.received_at ? new Date(d.received_at).toISOString() : null,
    })) as unknown as Mention[];

    return { data: items, total };
  });
}
