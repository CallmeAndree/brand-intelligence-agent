import { NextRequest } from "next/server";
import { proxyStreamToRuntime1 } from "@/lib/runtime1";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Proxy SSE sinh artifact → Runtime 1 POST /clusters/{id}/generate/stream.
// Stream từng delta text về UI (không buffer) để hiển thị realtime.
export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const body = await req.json().catch(() => ({}));
  return proxyStreamToRuntime1(`/clusters/${params.id}/generate/stream`, {
    method: "POST",
    body,
  });
}
