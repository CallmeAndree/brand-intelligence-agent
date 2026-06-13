"use client";

import DateRangeFilter from "@/components/DateRangeFilter";
import FilterChips from "@/components/FilterChips";
import MentionsTable from "@/components/MentionsTable";
import CriticalClusterList from "@/components/CriticalClusterList";
import ClusterWorkspace from "@/components/ClusterWorkspace";
import { FilterProvider } from "@/lib/filters";

export default function MonitorPage() {
  return (
    <FilterProvider>
      <main className="mx-auto max-w-content px-4 py-6">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Monitor &amp; phản ứng theo cụm
            </h1>
            <p className="text-sm text-ink/50">
              Chọn cụm critical → AI sinh nội dung → escalate hoặc gửi sang Chat
            </p>
          </div>
          <DateRangeFilter />
        </header>

        <div className="mb-4">
          <FilterChips />
        </div>

        {/* 2 cột: panel cụm critical (trái) + workspace chi tiết (phải) */}
        <section className="grid gap-4 lg:grid-cols-[minmax(280px,360px)_1fr]">
          <CriticalClusterList />
          <ClusterWorkspace />
        </section>

        {/* MentionsTable tự lọc theo clusterId đang chọn (FilterProvider) */}
        <section className="mt-6">
          <MentionsTable />
        </section>
      </main>
    </FilterProvider>
  );
}
