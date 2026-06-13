"use client";

import type { ChatMessage } from "@/lib/types";

// Bong bóng hội thoại — design/DESIGN.md: 2 màu palette phân biệt vai, bo 16px.
// user → feature-teal (text trắng, phải); assistant → surface cream (ink, trái).
// Slice sơ chỉ render `text`; chừa chỗ cho citations/charts ở slice sau.
export default function ChatMessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-[15px] leading-relaxed ${
          isUser
            ? "bg-feature-teal text-white"
            : "border border-ink/10 bg-feature-cream text-ink"
        }`}
      >
        {message.text}

        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.citations.map((c, i) => (
              <a
                key={i}
                href={c.url}
                target="_blank"
                rel="noreferrer"
                className="rounded-full bg-white/70 px-2 py-0.5 text-xs text-ink/70 underline"
              >
                {c.author || c.source || "nguồn"}
              </a>
            ))}
          </div>
        )}
        {/* charts[] (giai đoạn 3): render <EChart> inline — slice sau */}
      </div>
    </div>
  );
}
