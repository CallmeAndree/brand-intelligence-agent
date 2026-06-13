import { NextRequest } from "next/server";
import { proxyToRuntime1 } from "@/lib/runtime1";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Proxy sinh artifact → Runtime 1 POST /clusters/{id}/generate {type,variant?}.
export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const body = await req.json().catch(() => ({}));
  return proxyToRuntime1(`/clusters/${params.id}/generate`, {
    method: "POST",
    body,
  });
}
