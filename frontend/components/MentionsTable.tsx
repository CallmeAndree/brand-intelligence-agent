"use client";

import { useEffect, useState } from "react";
import { Card, Loading, ErrorBox, EmptyState } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters, filtersToQuery } from "@/lib/filters";
import { bandOf, bandColor } from "@/lib/severity";
import type { MentionsPage } from "@/lib/types";

const PAGE = 50;

export default function MentionsTable() {
  const { filters, setDim } = useFilters();
  const [skip, setSkip] = useState(0);

  // reset trang khi filter (trừ skip) đổi
  const filterKey = filtersToQuery(filters);
  useEffect(() => setSkip(0), [filterKey]);

  const { data, loading, validating, error } = useStats<MentionsPage>("/api/mentions", {
    skip,
    limit: PAGE,
  });

  const total = data?.total ?? 0;
  const toggle = (
    <label className="flex items-center gap-2 text-caption text-ink/70">
      <input
        type="checkbox"
        checked={!!filters.actionableOnly}
        onChange={(e) => setDim("actionableOnly", e.target.checked || undefined)}
      />
      Chỉ cần xử lý
    </label>
  );

  return (
    <Card
      title={`Danh sách mention${total ? ` (${total.toLocaleString("vi-VN")})` : ""}`}
      right={toggle}
      className="flex h-full min-h-0 flex-col"
    >
      {/* Stale-while-revalidate: chỉ blank lần đầu (chưa có data); đổi trang/filter giữ rows cũ. */}
      {loading && !data ? (
        <Loading />
      ) : error && !data ? (
        <ErrorBox message={error} />
      ) : !data || data.data.length === 0 ? (
        <EmptyState />
      ) : (
        <div className={`flex min-h-0 flex-1 flex-col transition-opacity ${validating ? "opacity-60" : ""}`}>
          <div className="min-h-0 flex-1 overflow-y-auto overflow-x-auto">
            <table className="w-full text-body-sm">
              <thead className="sticky top-0 z-10 bg-canvas text-left text-ink/50">
                <tr className="border-b border-ink/10">
                  <th className="py-2 pr-3 font-medium">Ngày</th>
                  <th className="py-2 pr-3 font-medium">Mức</th>
                  <th className="py-2 pr-3 font-medium">Nền tảng</th>
                  <th className="py-2 pr-3 font-medium">Ý định</th>
                  <th className="py-2 pr-3 font-medium">Mention</th>
                  <th className="py-2 font-medium">Link</th>
                </tr>
              </thead>
              <tbody>
                {data.data.map((m) => {
                  const band = bandOf(m.bi_severity);
                  return (
                    <tr key={m._id} className="border-b border-ink/5 align-top hover:bg-feature-cream/40">
                      <td className="py-2 pr-3 whitespace-nowrap text-ink/60">
                        {m.received_at ? m.received_at.slice(0, 10) : "—"}
                      </td>
                      <td className="py-2 pr-3">
                        {m.bi_severity != null ? (
                          <span
                            className="inline-block rounded px-1.5 py-0.5 text-caption font-semibold text-white"
                            style={{ backgroundColor: band ? bandColor(band) : "#c9c2b0" }}
                          >
                            {m.bi_severity}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-2 pr-3 whitespace-nowrap text-ink/70">
                        {m.platform ?? m.source ?? "—"}
                      </td>
                      <td className="py-2 pr-3 text-ink/70">{m.bi_intent ?? "—"}</td>
                      <td className="py-2 pr-3 max-w-[420px] whitespace-pre-wrap break-words">
                        {m.mention?.trim() || "—"}
                      </td>
                      <td className="py-2">
                        {m.url ? (
                          <a
                            href={m.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-feature-blue underline"
                          >
                            mở
                          </a>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex shrink-0 items-center justify-between text-body-sm text-ink/60">
            <span>
              {skip + 1}–{Math.min(skip + PAGE, total)} / {total.toLocaleString("vi-VN")}
            </span>
            <div className="flex gap-2">
              <button
                disabled={skip === 0}
                onClick={() => setSkip(Math.max(0, skip - PAGE))}
                className="rounded-[10px] border border-ink/15 px-3 py-1 disabled:opacity-40"
              >
                Trước
              </button>
              <button
                disabled={skip + PAGE >= total}
                onClick={() => setSkip(skip + PAGE)}
                className="rounded-[10px] border border-ink/15 px-3 py-1 disabled:opacity-40"
              >
                Sau
              </button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
