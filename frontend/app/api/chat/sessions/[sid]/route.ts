import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// GET /api/chat/sessions/[sid]?user_id=demo → liệt kê event của 1 phiên.
// Proxy sang Runtime 2 (kind=list_events), giữ credential/header phía server.
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ sid: string }> },
) {
  const { sid } = await params;
  const baseUrl = process.env.AGENT_BASE_URL;
  if (!baseUrl) return NextResponse.json({ events: [] });
  const userId = req.nextUrl.searchParams.get("user_id") ?? "demo";
  try {
    const res = await fetch(`${baseUrl.replace(/\/$/, "")}/invocations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-GreenNode-AgentBase-User-Id": userId,
        "X-GreenNode-AgentBase-Session-Id": sid,
      },
      body: JSON.stringify({ kind: "list_events", user_id: userId, session_id: sid }),
    });
    if (!res.ok) return NextResponse.json({ events: [] });
    const data = await res.json();
    return NextResponse.json({ events: data?.events ?? [] });
  } catch (err) {
    console.error("[api/chat/sessions/[sid]]", err);
    return NextResponse.json({ events: [] });
  }
}

// DELETE /api/chat/sessions/[sid]?user_id=demo → xóa cả phiên (toàn bộ event).
// Proxy sang Runtime 2 (kind=delete_session); backend lặp xóa từng event.
export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ sid: string }> },
) {
  const { sid } = await params;
  const baseUrl = process.env.AGENT_BASE_URL;
  if (!baseUrl) return NextResponse.json({ deleted: 0, success: false });
  const userId = req.nextUrl.searchParams.get("user_id") ?? "demo";
  try {
    const res = await fetch(`${baseUrl.replace(/\/$/, "")}/invocations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-GreenNode-AgentBase-User-Id": userId,
        "X-GreenNode-AgentBase-Session-Id": sid,
      },
      body: JSON.stringify({ kind: "delete_session", user_id: userId, session_id: sid }),
    });
    if (!res.ok) return NextResponse.json({ deleted: 0, success: false });
    const data = await res.json();
    return NextResponse.json({
      deleted: data?.deleted ?? 0,
      success: data?.success ?? false,
    });
  } catch (err) {
    console.error("[api/chat/sessions/[sid] DELETE]", err);
    return NextResponse.json({ deleted: 0, success: false });
  }
}
