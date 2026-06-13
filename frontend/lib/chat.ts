"use client";

import type { ChatMessage } from "./types";

// Slice sơ: session client-side. session_id ổn định trong phiên trình duyệt
// (localStorage), user_id cố định cho demo. Payload mang sẵn cả hai để backend
// sau (Runtime 2 AgentBase) đọc được — slice này chưa dùng để personalize.

const SESSION_KEY = "bi_chat_session_id";
const DEMO_USER_ID = "demo";

export function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export function getUserId(): string {
  return DEMO_USER_ID;
}

// Bắt đầu phiên mới (nút "phiên mới").
export function resetSession(): string {
  const id = crypto.randomUUID();
  if (typeof window !== "undefined") {
    window.localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

// Gửi message tới proxy /api/chat. Proxy luôn trả ChatMessage (kể cả lỗi → text
// thông báo), nên chỉ ném khi network/parse hỏng hoàn toàn.
export async function sendMessage(message: string): Promise<ChatMessage> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: getSessionId(),
      user_id: getUserId(),
      message,
    }),
  });
  const data = (await res.json()) as ChatMessage;
  return { ...data, role: "assistant", text: data.text ?? "" };
}

// ---- Cầu nối Monitor → Chat (context inject) ----
// Monitor "Gửi sang Chat" → lưu artifact tạm vào sessionStorage rồi điều hướng /chat;
// ChatWindow đọc khi mount, gửi 1 message kind="context_inject" để Runtime 2 ghi memory.
const INJECT_KEY = "bi_pending_context_inject";

export interface ContextInject {
  content_md: string;
  cluster_id: number;
}

export function queueContextInject(payload: ContextInject): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(INJECT_KEY, JSON.stringify(payload));
  }
}

export function takeQueuedContextInject(): ContextInject | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(INJECT_KEY);
  if (!raw) return null;
  window.sessionStorage.removeItem(INJECT_KEY);
  try {
    return JSON.parse(raw) as ContextInject;
  } catch {
    return null;
  }
}

// Gửi context_inject sang Runtime 2 (ghi memory). Trả ChatMessage xác nhận.
export async function sendContextInject(inject: ContextInject): Promise<ChatMessage> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: getSessionId(),
      user_id: getUserId(),
      kind: "context_inject",
      content_md: inject.content_md,
      cluster_id: inject.cluster_id,
    }),
  });
  const data = (await res.json()) as ChatMessage;
  return { ...data, role: "assistant", text: data.text ?? "" };
}
