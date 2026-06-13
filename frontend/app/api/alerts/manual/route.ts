import { NextRequest } from "next/server";
import { proxyToRuntime1 } from "@/lib/runtime1";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Proxy phát alert thủ công → Runtime 1 POST /alerts/manual {cluster_id}.
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  return proxyToRuntime1("/alerts/manual", { method: "POST", body });
}
