import { NextRequest } from "next/server";
import { mentionsCollection } from "@/lib/mongo";
import { parseFilters, buildMatch } from "@/lib/aggregations";
import { handle } from "@/lib/response";
import type { CountItem } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Nhãn nền tảng chuẩn — gom các biến thể hoa/thường về một slice (vd "facebook" → "Facebook").
const CANONICAL_PLATFORM: Record<string, string> = {
  facebook: "Facebook",
  tiktok: "TikTok",
  youtube: "YouTube",
  threads: "Threads",
  instagram: "Instagram",
  voz: "Voz",
  unknown: "unknown",
};

function canonicalLabel(raw: string): { key: string; label: string } {
  const norm = raw.trim();
  const lower = norm.toLowerCase();
  // key gom theo lowercase (Facebook == facebook); label ưu tiên nhãn chuẩn, không có thì giữ nguyên bản gốc.
  return { key: lower || "unknown", label: CANONICAL_PLATFORM[lower] ?? (norm || "unknown") };
}

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

    // Gom các biến thể hoa/thường của cùng nền tảng (Facebook + facebook) thành một slice.
    const merged = new Map<string, { label: string; count: number }>();
    for (const r of rows) {
      const { key, label } = canonicalLabel(String(r._id ?? "unknown"));
      const cur = merged.get(key);
      if (cur) cur.count += r.count as number;
      else merged.set(key, { label, count: r.count as number });
    }
    return [...merged.values()]
      .map((v) => ({ key: v.label, count: v.count }))
      .sort((a, b) => b.count - a.count);
  });
}
