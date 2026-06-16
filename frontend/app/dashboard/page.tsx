"use client";

import { FilterProvider, useFilters } from "@/lib/filters";
import DateRangeFilter from "@/components/DateRangeFilter";
import FilterChips from "@/components/FilterChips";
import KpiStrip from "@/components/KpiStrip";
import TimelineTrend from "@/components/TimelineTrend";
import KeywordCloud from "@/components/KeywordCloud";
import PlatformDonut from "@/components/PlatformDonut";
import ProductAreaBar from "@/components/ProductAreaBar";
import TopicChart from "@/components/TopicChart";
import RiskScatter from "@/components/RiskScatter";

function DashboardBody() {
  const { clearAll } = useFilters();

  return (
    <main className="mx-auto max-w-content px-4 py-6">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-label uppercase text-ink/40">Social Listening</p>
          <h1 className="text-title-lg">
            Zalopay 505
          </h1>
          <p className="text-body-sm text-ink/50">
            Giám sát &amp; phân tích thảo luận tiêu cực về Zalopay trên mạng xã hội
          </p>
        </div>
        <DateRangeFilter />
      </header>

      <div className="mb-4">
        <FilterChips />
      </div>

      <section className="mb-4">
        <KpiStrip />
      </section>

      {/* Lưới 12 cột bất đối xứng: chart bề-ngang rộng hơn chart phụ cùng hàng,
          không hàng nào 2 ô bằng nhau (8/4 · 8/4 · 7/5). Mobile/tablet stack 1 cột.
          onClick trên grid: click trúng KHOẢNG TRỐNG giữa các chart (target === grid)
          → bỏ filter; click vào card/chart không lọt vào đây (target là con). */}
      <section
        className="mb-4 grid grid-cols-1 items-stretch gap-4 lg:grid-cols-12 [&>div>*]:h-full"
        onClick={(e) => {
          if (e.target === e.currentTarget) clearAll();
        }}
      >
        <div className="lg:col-span-8">
          <TimelineTrend />
        </div>
        <div className="lg:col-span-4">
          <PlatformDonut />
        </div>
        <div className="lg:col-span-4">
          <KeywordCloud />
        </div>
        <div className="lg:col-span-8">
          <TopicChart />
        </div>
        <div className="lg:col-span-7">
          <ProductAreaBar />
        </div>
        <div className="lg:col-span-5">
          <RiskScatter />
        </div>
      </section>
    </main>
  );
}

export default function DashboardPage() {
  return (
    <FilterProvider>
      <DashboardBody />
    </FilterProvider>
  );
}
