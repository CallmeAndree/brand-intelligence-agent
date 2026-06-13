"use client";

import { useState } from "react";
import Markdown from "./Markdown";
import type { MonitorArtifact } from "@/lib/types";

const TYPE_LABEL: Record<string, string> = {
  narrative: "Narrative",
  root_cause: "Nguyên nhân gốc",
  response_strategy: "Chiến lược phản hồi",
  brand_voice: "Brand voice",
  seeding_comments: "Seeding",
};

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-feature-ochre/20 text-ink/70",
  approved: "bg-feature-teal/15 text-feature-teal",
  discarded: "bg-ink/10 text-ink/40",
};

export default function ArtifactCard({
  artifact,
  onApprove,
  onDiscard,
  onRegenerate,
  onSendToChat,
  busy,
}: {
  artifact: MonitorArtifact;
  onApprove: () => void;
  onDiscard: () => void;
  onRegenerate: () => void;
  onSendToChat: () => void;
  busy?: boolean;
}) {
  const variants = artifact.variants ?? null;
  const [activeVariant, setActiveVariant] = useState(0);
  const isDraft = artifact.status === "draft";

  return (
    <div className="rounded-card border border-ink/10 bg-white/70 p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-ink/90">
            {TYPE_LABEL[artifact.type] ?? artifact.type}
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              STATUS_STYLE[artifact.status] ?? ""
            }`}
          >
            {artifact.status}
          </span>
        </div>
        {artifact.created_at && (
          <span className="text-xs text-ink/40">
            {artifact.created_at.slice(0, 16).replace("T", " ")}
          </span>
        )}
      </div>

      {variants && variants.length > 0 ? (
        <>
          <div className="mb-2 flex flex-wrap gap-1.5">
            {variants.map((v, i) => (
              <button
                key={i}
                onClick={() => setActiveVariant(i)}
                className={`rounded-full px-2.5 py-1 text-xs transition ${
                  i === activeVariant
                    ? "bg-feature-lavender/40 font-medium text-ink"
                    : "bg-ink/5 text-ink/60 hover:bg-ink/10"
                }`}
              >
                {v.label}
              </button>
            ))}
          </div>
          <Markdown>{variants[activeVariant]?.content_md ?? ""}</Markdown>
        </>
      ) : (
        <Markdown>{artifact.content_md}</Markdown>
      )}

      <div className="mt-3 flex flex-wrap gap-2 border-t border-ink/5 pt-3 text-sm">
        {isDraft && (
          <>
            <button
              onClick={onApprove}
              disabled={busy}
              className="rounded-[10px] bg-feature-teal px-3 py-1 text-white disabled:opacity-40"
            >
              Lưu
            </button>
            <button
              onClick={onDiscard}
              disabled={busy}
              className="rounded-[10px] border border-ink/15 px-3 py-1 text-ink/70 disabled:opacity-40"
            >
              Bỏ
            </button>
          </>
        )}
        <button
          onClick={onRegenerate}
          disabled={busy}
          className="rounded-[10px] border border-ink/15 px-3 py-1 text-ink/70 disabled:opacity-40"
        >
          Tái sinh
        </button>
        <button
          onClick={onSendToChat}
          disabled={busy}
          className="rounded-[10px] border border-feature-pink/40 px-3 py-1 text-feature-pink disabled:opacity-40"
        >
          ➡ Gửi sang Chat
        </button>
      </div>
    </div>
  );
}
