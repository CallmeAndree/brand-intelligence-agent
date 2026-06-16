"use client";

import { useState } from "react";

// Ô nhập + nút gửi. Enter để gửi (Shift+Enter xuống dòng). Disable khi đang chờ.
// text-input/button theo design/DESIGN.md: bo 12px (rounded-xl), height ~44px.
export default function ChatInput({
  onSend,
  disabled,
  placeholder = "Hỏi về mention tiêu cực của Zalopay…",
}: {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const [value, setValue] = useState("");

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
  };

  return (
    <div className="flex items-end gap-2">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={1}
        disabled={disabled}
        placeholder={placeholder}
        className="max-h-40 min-h-[44px] flex-1 resize-none rounded-xl border border-ink/15 bg-canvas px-4 py-3 text-body-md text-ink outline-none placeholder:text-ink/40 focus:border-ink/40 disabled:cursor-not-allowed disabled:opacity-50"
      />
      <button
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="h-11 shrink-0 rounded-xl bg-ink px-5 text-button text-white transition disabled:opacity-40"
      >
        Gửi
      </button>
    </div>
  );
}
