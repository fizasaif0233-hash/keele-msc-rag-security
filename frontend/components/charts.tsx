"use client";

import { EmptyState } from "@/components/ui";
import type { Report } from "@/lib/types";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function EvaluationCharts({ report }: { report: Report }) {
  if (!report.has_results) {
    return <EmptyState title="No measured trials" body="Charts stay empty until at least one trial completes without an infrastructure failure." />;
  }

  const summary = [
    { name: "Attack success", baseline: report.by_configuration.baseline.attack_success_rate, secured: report.by_configuration.secured.attack_success_rate },
    { name: "Disclosure", baseline: report.by_configuration.baseline.disclosure_rate, secured: report.by_configuration.secured.disclosure_rate },
    { name: "Legitimate success", baseline: report.by_configuration.baseline.legitimate_task_success_rate, secured: report.by_configuration.secured.legitimate_task_success_rate },
  ].filter((row) => row.baseline !== null || row.secured !== null);

  const latency = [
    { name: "Average", baseline: report.by_configuration.baseline.average_latency_ms, secured: report.by_configuration.secured.average_latency_ms },
    { name: "Median", baseline: report.by_configuration.baseline.median_latency_ms, secured: report.by_configuration.secured.median_latency_ms },
    { name: "95th percentile", baseline: report.by_configuration.baseline.p95_latency_ms, secured: report.by_configuration.secured.p95_latency_ms },
  ].filter((row) => row.baseline !== null || row.secured !== null);

  const categories = new Map<string, { category: string; baseline: number | null; secured: number | null }>();
  report.category_breakdown
    .filter((row) => row.category !== "benign" && row.attack_success_rate !== null)
    .forEach((row) => {
      const current = categories.get(row.category) || { category: row.category.replaceAll("_", " "), baseline: null, secured: null };
      if (row.configuration === "baseline") current.baseline = row.attack_success_rate;
      if (row.configuration === "secured") current.secured = row.attack_success_rate;
      categories.set(row.category, current);
    });

  const outcomes = new Map<string, { outcome: string; baseline: number; secured: number }>();
  report.outcome_distribution.forEach((row) => {
    const current = outcomes.get(row.outcome) || { outcome: row.outcome, baseline: 0, secured: 0 };
    if (row.configuration === "baseline") current.baseline = row.count;
    if (row.configuration === "secured") current.secured = row.count;
    outcomes.set(row.outcome, current);
  });

  return (
    <div className="space-y-6">
      <ChartCard title="Attack, disclosure, and legitimate-task rates" data={summary} unit="%" />
      <ChartCard title="Response latency" data={latency} unit=" ms" />
      {categories.size > 0 ? (
        <ChartCard title="Attack success by category" data={[...categories.values()]} unit="%" />
      ) : (
        <EmptyState title="No category attack rates" body="Category rates appear when attack trials in that category are measured." />
      )}
      {outcomes.size > 0 && <ChartCard title="Trial outcome distribution" data={[...outcomes.values()]} unit="" />}
    </div>
  );
}

function ChartCard({
  title,
  data,
  unit,
}: {
  title: string;
  data: Array<Record<string, string | number | null>>;
  unit: string;
}) {
  return (
    <section className="rounded-2xl border border-line bg-card p-5">
      <h3 className="mb-4 font-semibold">{title}</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, value === null ? undefined : value])))}>
            <CartesianGrid stroke="#24304a" vertical={false} />
            <XAxis dataKey={Object.keys(data[0] || {}).includes("category") ? "category" : Object.keys(data[0] || {}).includes("outcome") ? "outcome" : "name"} stroke="#93a0b8" tick={{ fill: "#93a0b8", fontSize: 12 }} />
            <YAxis stroke="#93a0b8" tick={{ fill: "#93a0b8", fontSize: 12 }} />
            <Tooltip formatter={(value) => (value === null || value === undefined ? "No measured trials" : `${value}${unit}`)} />
            <Legend />
            <Bar dataKey="baseline" fill="#7aa2ff" radius={[4, 4, 0, 0]} />
            <Bar dataKey="secured" fill="#b39cff" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
