import { NextRequest } from "next/server";
import { proxyToRuntime1 } from "@/lib/runtime1";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Proxy duyệt/bỏ artifact → Runtime 1 POST /artifacts/{id}/{approve|discard}.
export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string; action: string } },
) {
  return proxyToRuntime1(`/artifacts/${params.id}/${params.action}`, {
    method: "POST",
  });
}
