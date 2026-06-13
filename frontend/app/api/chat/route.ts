import { NextRequest, NextResponse } from "next/server";
import type { ChatMessage } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Slice add-chat-skeleton: proxy MỎNG → Runtime 2 (Chat Analyst, AgentBase SDK)
// endpoint POST /invocations. KHÔNG system prompt, KHÔNG gọi LLM ở đây — agent
// logic sống ở Runtime 2 (brand-intelligence-agent/agent/). Route này chỉ:
//  - giữ credential phía server (browser chỉ thấy /api/chat),
//  - gắn header session/user mà AgentBase Memory service đọc (slice sau).
// Khi Runtime 2 lên AgentBase: chỉ đổi AGENT_BASE_URL trong .env.local.

const PROXY_TIMEOUT_MS = 30_000;

interface ChatRequestBody {
  session_id?: string;
  user_id?: string;
  message?: string;
  kind?: string;
  content_md?: string;
  cluster_id?: number;
}

// Luôn trả ChatMessage assistant (HTTP 200) → UI render bubble (kể cả lỗi).
function assistant(text: string): NextResponse<ChatMessage> {
  return NextResponse.json({ role: "assistant", text });
}

export async function POST(req: NextRequest) {
  let body: ChatRequestBody;
  try {
    body = (await req.json()) as ChatRequestBody;
  } catch {
    return assistant("Yêu cầu không hợp lệ (không đọc được nội dung).");
  }

  const isInject = body.kind === "context_inject";
  const message = body.message?.trim();
  // context_inject không cần message text — chỉ cần content_md.
  if (!isInject && !message) return assistant("Bạn hãy nhập câu hỏi nhé.");

  const baseUrl = process.env.AGENT_BASE_URL;
  if (!baseUrl) {
    console.error("[api/chat] thiếu AGENT_BASE_URL");
    return assistant("Chat chưa được cấu hình (thiếu endpoint agent).");
  }

  const sessionId = body.session_id ?? "";
  const userId = body.user_id ?? "demo";

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);
  try {
    const res = await fetch(`${baseUrl.replace(/\/$/, "")}/invocations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-GreenNode-AgentBase-Session-Id": sessionId,
        "X-GreenNode-AgentBase-User-Id": userId,
      },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        user_id: userId,
        kind: body.kind,
        content_md: body.content_md,
        cluster_id: body.cluster_id,
      }),
      signal: controller.signal,
    });

    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      console.error("[api/chat] Runtime 2 lỗi", res.status, detail.slice(0, 500));
      return assistant(`Xin lỗi, dịch vụ trả lời đang gặp sự cố (mã ${res.status}). Bạn thử lại sau nhé.`);
    }

    // Runtime 2 trả ChatMessage JSON. Chuẩn hóa phòng thủ role/text.
    const data = (await res.json()) as Partial<ChatMessage>;
    return NextResponse.json<ChatMessage>({
      ...data,
      role: "assistant",
      text: data.text ?? "",
    });
  } catch (err) {
    const aborted = err instanceof Error && err.name === "AbortError";
    console.error("[api/chat]", err);
    return assistant(
      aborted
        ? "Yêu cầu mất quá nhiều thời gian (timeout). Bạn thử lại nhé."
        : "Không kết nối được tới dịch vụ trả lời. Bạn thử lại sau nhé."
    );
  } finally {
    clearTimeout(timer);
  }
}
