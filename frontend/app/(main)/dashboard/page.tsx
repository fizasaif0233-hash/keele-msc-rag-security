"use client";

import { Alert, Badge, Card, EmptyState } from "@/components/ui";
import { api } from "@/lib/api";
import type { Experiment, MetricSummary, SecurityEvent } from "@/lib/types";
import { formatMs, formatRate, formatWhen } from "@/lib/utils";
import Link from "next/link";
import { useEffect, useState } from "react";

type Dashboard = {
  role: string;
  documents: number;
  test_cases: number | null;
  experiments: number | null;
  chat_sessions: number;
  has_results: boolean;
  metrics: { baseline: MetricSummary; secured: MetricSummary } | null;
  recent_events: SecurityEvent[];
  latest_experiment: Experiment | null;
};

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Dashboard>("/api/v1/dashboard")
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  if (error) return <Alert tone="bad">{error}</Alert>;
  if (!data) return <p className="text-muted">Loading records…</p>;

  const cards = [
    ["Documents you can access", String(data.documents)],
    ["Your chat sessions", String(data.chat_sessions)],
    ["Test cases", data.test_cases === null ? "Restricted" : String(data.test_cases)],
    ["Experiments", data.experiments === null ? "Restricted" : String(data.experiments)],
  ];

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold">Dashboard</h2>
        <p className="mt-1 text-sm text-muted">Counts and rates come from stored records. Empty rates mean no completed trials have been measured.</p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(([label, value]) => (
          <Card key={label}>
            <p className="text-sm text-muted">{label}</p>
            <p className="mt-2 text-3xl font-semibold">{value}</p>
          </Card>
        ))}
      </div>
      {data.metrics ? (
        <div className="grid gap-4 md:grid-cols-2">
          <MetricCard title="Baseline" metric={data.metrics.baseline} />
          <MetricCard title="Secured" metric={data.metrics.secured} />
        </div>
      ) : (
        <EmptyState
          title={data.role === "employee" ? "Research metrics are limited to research roles" : "No completed experiment trials"}
          body={data.role === "employee" ? "You can manage authorised documents and use the secured chat." : "Run a baseline and a secured experiment to calculate attack, disclosure, utility, and latency figures."}
        />
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="font-semibold">Latest experiment</h3>
          {data.latest_experiment ? (
            <div className="mt-3 space-y-2 text-sm">
              <p>{data.latest_experiment.name}</p>
              <p className="text-muted">{data.latest_experiment.configuration} · {data.latest_experiment.status}</p>
              <p className="text-muted">{data.latest_experiment.progress_completed} / {data.latest_experiment.progress_total} trials</p>
              {data.role !== "employee" && <Link className="text-accent" href={`/experiments/${data.latest_experiment.id}`}>Open run</Link>}
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted">No experiment has been created.</p>
          )}
        </Card>
        <Card>
          <h3 className="font-semibold">Recent security events</h3>
          {data.recent_events.length === 0 ? (
            <p className="mt-3 text-sm text-muted">No security events have been recorded.</p>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {data.recent_events.map((event) => (
                <li key={event.id} className="flex items-start justify-between gap-3">
                  <span>{event.event_type.replaceAll("_", " ")}</span>
                  <span className="text-muted">{formatWhen(event.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function MetricCard({ title, metric }: { title: string; metric: MetricSummary }) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">{title}</h3>
        <Badge>{metric.completed_trials} measured trials</Badge>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div><dt className="text-muted">Attack success</dt><dd>{formatRate(metric.attack_success_rate)}</dd></div>
        <div><dt className="text-muted">Disclosure</dt><dd>{formatRate(metric.disclosure_rate)}</dd></div>
        <div><dt className="text-muted">Legitimate success</dt><dd>{formatRate(metric.legitimate_task_success_rate)}</dd></div>
        <div><dt className="text-muted">Average latency</dt><dd>{formatMs(metric.average_latency_ms)}</dd></div>
      </dl>
    </Card>
  );
}
