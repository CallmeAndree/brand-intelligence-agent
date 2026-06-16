import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// GET /api/chat/sessions?user_id=demo → liệt kê phiên hội thoại của actor.
// Proxy sang Runtime 2 (kind=list_sessions), giữ credential/header phía server.
export async function POST(req: NextRequest) {
  return invoke(req);
}

export async function GET(req: NextRequest) {
  return invoke(req);
}

async function invoke(req: NextRequest) {
  const baseUrl = process.env.AGENT_BASE_URL;
  if (!baseUrl) return NextResponse.json({ sessions: [] });
  const userId = req.nextUrl.searchParams.get("user_id") ?? "demo";
  try {
    const res = await fetch(`${baseUrl.replace(/\/$/, "")}/invocations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-GreenNode-AgentBase-User-Id": userId,
      },
      body: JSON.stringify({ kind: "list_sessions", user_id: userId }),
    });
    if (!res.ok) return NextResponse.json({ sessions: [] });
    const data = await res.json();
    return NextResponse.json({ sessions: data?.sessions ?? [] });
  } catch (err) {
    console.error("[api/chat/sessions]", err);
    return NextResponse.json({ sessions: [] });
  }
}
