import { NextResponse } from "next/server";

// Proxy server-side sang Runtime 1 (generation/alerting). Giấu RUNTIME1_API_TOKEN
// khỏi browser — giống cách /api/chat giấu khi gọi Runtime 2. Body forward nguyên.

const TIMEOUT_MS = 120_000;

export function runtime1Configured(): boolean {
  return !!process.env.RUNTIME1_BASE_URL;
}

export async function proxyToRuntime1(
  path: string,
  init: { method: string; body?: unknown },
): Promise<NextResponse> {
  const base = process.env.RUNTIME1_BASE_URL;
  if (!base) {
    return NextResponse.json(
      { success: false, message: "RUNTIME1_BASE_URL chưa cấu hình" },
      { status: 503 },
    );
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${base.replace(/\/$/, "")}${path}`, {
      method: init.method,
      headers: {
        "Content-Type": "application/json",
        "X-Runtime1-Token": process.env.RUNTIME1_API_TOKEN || "",
      },
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      signal: controller.signal,
      cache: "no-store",
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    const aborted = err instanceof Error && err.name === "AbortError";
    return NextResponse.json(
      {
        success: false,
        message: aborted ? "Runtime 1 timeout" : "Không kết nối được Runtime 1",
      },
      { status: 502 },
    );
  } finally {
    clearTimeout(timer);
  }
}

// Proxy SSE: forward thẳng ReadableStream từ Runtime 1 về browser (không buffer)
// để UI nhận token realtime. Dùng cho /clusters/{id}/generate/stream.
export async function proxyStreamToRuntime1(
  path: string,
  init: { method: string; body?: unknown },
): Promise<Response> {
  const base = process.env.RUNTIME1_BASE_URL;
  const sseError = (msg: string, status: number) =>
    new Response(`event: error\ndata: ${JSON.stringify({ message: msg })}\n\n`, {
      status,
      headers: { "Content-Type": "text/event-stream" },
    });

  if (!base) return sseError("RUNTIME1_BASE_URL chưa cấu hình", 503);
  try {
    const res = await fetch(`${base.replace(/\/$/, "")}${path}`, {
      method: init.method,
      headers: {
        "Content-Type": "application/json",
        "X-Runtime1-Token": process.env.RUNTIME1_API_TOKEN || "",
      },
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      cache: "no-store",
    });
    if (!res.ok || !res.body) {
      const detail = await res.text().catch(() => "");
      return sseError(`Runtime 1 lỗi ${res.status}: ${detail.slice(0, 200)}`, 200);
    }
    return new Response(res.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  } catch {
    return sseError("Không kết nối được Runtime 1", 200);
  }
}
