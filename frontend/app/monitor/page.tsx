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
      {/* min-h viewport: cả 2 vùng có chiều cao cố định lớn → cùng dài ra + cuộn nội bộ;
          trang cuộn dọc khi tổng vượt viewport (không zero-sum như khi khóa cứng 1 màn hình). */}
      <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-content flex-col px-4 py-6">
        <header className="mb-4 flex shrink-0 flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-title-lg">
              Monitor
            </h1>
          </div>
          <DateRangeFilter />
        </header>

        <div className="mb-4 shrink-0">
          <FilterChips />
        </div>

        {/* Vùng cụm: chiều cao xác định (h-[90vh]) → 2 panel luôn cao bằng nhau và dài thoáng,
            mỗi panel tự cuộn nội bộ (Card scroll + h-full). grid-rows-2 ở mobile để 2 panel chia đều. */}
        <section className="grid h-[90vh] grid-rows-2 shrink-0 gap-4 lg:grid-rows-1 lg:grid-cols-[minmax(280px,360px)_1fr]">
          <div className="min-h-0">
            <CriticalClusterList />
          </div>
          <div className="min-h-0">
            <ClusterWorkspace />
          </div>
        </section>

        {/* Vùng mention: chiều cao cố định lớn (h-[78vh]) → bảng dài, cuộn nội bộ riêng (thead sticky).
            Tự lọc theo clusterId đang chọn. */}
        <section className="mt-4 h-[78vh] shrink-0">
          <MentionsTable />
        </section>
      </main>
    </FilterProvider>
  );
}
