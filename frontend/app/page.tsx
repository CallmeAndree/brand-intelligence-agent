"use client";

import { FilterProvider } from "@/lib/filters";
import DateRangeFilter from "@/components/DateRangeFilter";
import FilterChips from "@/components/FilterChips";
import KpiStrip from "@/components/KpiStrip";
import TimelineTrend from "@/components/TimelineTrend";
import KeywordCloud from "@/components/KeywordCloud";
import PlatformDonut from "@/components/PlatformDonut";
import ProductAreaBar from "@/components/ProductAreaBar";
import TopicChart from "@/components/TopicChart";

export default function DashboardPage() {
  return (
    <FilterProvider>
      <main className="mx-auto max-w-content px-4 py-6">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Brand Intelligence
            </h1>
            <p className="text-sm text-ink/50">
              Theo dõi mention negative về ZaloPay
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

        {/* Timeline (2/3) + Platform donut (1/3) */}
        <section className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <TimelineTrend />
          </div>
          <div>
            <PlatformDonut />
          </div>
        </section>

        {/* Keyword + Product area + Topic */}
        <section className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <KeywordCloud />
          <ProductAreaBar />
          <TopicChart />
        </section>
      </main>
    </FilterProvider>
  );
}
