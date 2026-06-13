"use client";

import { useEffect, useRef, useState } from "react";
import ChatMessageBubble from "./ChatMessageBubble";
import ChatInput from "./ChatInput";
import {
  sendMessage,
  resetSession,
  takeQueuedContextInject,
  sendContextInject,
} from "@/lib/chat";
import type { ChatMessage } from "@/lib/types";

const GREETING: ChatMessage = {
  role: "assistant",
  text: "Chào bạn 👋 Mình là Brand Intelligence Analyst. Hỏi mình về các mention tiêu cực của ZaloPay nhé.",
};

export default function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING]);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // auto-scroll xuống cuối khi có message mới hoặc đang gõ.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, sending]);

  // Nếu đến từ Monitor "Gửi sang Chat": nạp artifact làm ngữ cảnh (ghi memory) 1 lần.
  useEffect(() => {
    const inject = takeQueuedContextInject();
    if (!inject) return;
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        text: `📎 Đã nạp ngữ cảnh artifact của cụm #${inject.cluster_id} vào phiên chat. Bạn có thể yêu cầu mình viết tiếp dựa trên nội dung này.`,
      },
    ]);
    void sendContextInject(inject).catch(() => undefined);
  }, []);

  const handleSend = async (text: string) => {
    setMessages((prev) => [...prev, { role: "user", text }]);
    setSending(true);
    try {
      const reply = await sendMessage(text);
      setMessages((prev) => [...prev, reply]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "Không kết nối được tới dịch vụ trả lời. Bạn thử lại nhé.",
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const newSession = () => {
    resetSession();
    setMessages([GREETING]);
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-9rem)] max-w-[760px] flex-col">
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Chat Analyst</h1>
        <button
          onClick={newSession}
          className="rounded-xl border border-ink/15 px-3 py-1.5 text-sm text-ink/70 transition hover:bg-white/60"
        >
          Phiên mới
        </button>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 space-y-3 overflow-y-auto rounded-2xl border border-ink/10 bg-white/40 p-4"
      >
        {messages.map((m, i) => (
          <ChatMessageBubble key={i} message={m} />
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="rounded-2xl border border-ink/10 bg-feature-cream px-4 py-3 text-[15px] text-ink/50">
              <span className="inline-flex gap-1">
                <span className="animate-bounce">•</span>
                <span className="animate-bounce [animation-delay:0.15s]">
                  •
                </span>
                <span className="animate-bounce [animation-delay:0.3s]">•</span>
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="mt-3">
        <ChatInput onSend={handleSend} disabled={sending} />
      </div>
    </div>
  );
}
