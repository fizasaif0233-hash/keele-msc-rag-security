"use client";

import { EvaluationCharts } from "@/components/charts";
import { Alert, Button, Card, EmptyState } from "@/components/ui";
import { api, apiBlob } from "@/lib/api";
import type { Experiment, Report } from "@/lib/types";
import { formatMs, formatRate } from "@/lib/utils";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function AnalyticsPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ report: Report; experiments: Experiment[] }>("/api/v1/analytics")
      .then((response) => {
        setReport(response.report);
        setExperiments(response.experiments);
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function download(format: "csv" | "json") {
    const blob = await apiBlob(`/api/v1/analytics/export?format=${format}`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `experiment-results.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  }

  if (error) return <Alert tone="bad">{error}</Alert>;
  if (!report) return <p className="text-muted">Loading evaluation records…</p>;
  const baseline = report.by_configuration.baseline;
  const secured = report.by_configuration.secured;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Evaluation</h2>
          <p className="mt-1 max-w-3xl text-sm text-muted">Infrastructure failures are excluded from rates. A percentage reduction is omitted when the baseline rate is missing or zero.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => download("csv")}>Export CSV</Button>
          <Button variant="ghost" onClick={() => download("json")}>Export JSON</Button>
        </div>
      </header>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h3 className="font-semibold">Baseline</h3>
          <RateList metric={baseline} />
        </Card>
        <Card>
          <h3 className="font-semibold">Secured</h3>
          <RateList metric={secured} />
        </Card>
      </div>
      {report.reductions ? (
        <Card>
          <h3 className="font-semibold">Difference</h3>
          <dl className="mt-3 grid gap-3 text-sm md:grid-cols-2">
            <div>
              <dt className="text-muted">Attack success reduction</dt>
              <dd>{report.reductions.attack_success_rate.percentage_reduction === null ? report.reductions.attack_success_rate.note : `${report.reductions.attack_success_rate.percentage_reduction.toFixed(1)}%`}</dd>
              <dd className="text-muted">Absolute: {report.reductions.attack_success_rate.absolute_reduction ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted">Disclosure reduction</dt>
              <dd>{report.reductions.disclosure_rate.percentage_reduction === null ? report.reductions.disclosure_rate.note : `${report.reductions.disclosure_rate.percentage_reduction.toFixed(1)}%`}</dd>
              <dd className="text-muted">Absolute: {report.reductions.disclosure_rate.absolute_reduction ?? "—"}</dd>
            </div>
          </dl>
        </Card>
      ) : null}
      <EvaluationCharts report={report} />
      <Card>
        <h3 className="mb-3 font-semibold">Experiment history</h3>
        {experiments.length === 0 ? (
          <EmptyState title="No experiments" body="Experiment history is shown after a run is created." />
        ) : (
          <div className="overflow-auto">
            <table>
              <thead><tr><th>Name</th><th>Configuration</th><th>Status</th><th>Trials</th></tr></thead>
              <tbody>
                {experiments.map((experiment) => (
                  <tr key={experiment.id}>
                    <td><Link className="text-accent" href={`/experiments/${experiment.id}`}>{experiment.name}</Link></td>
                    <td>{experiment.configuration}</td>
                    <td>{experiment.status}</td>
                    <td>{experiment.progress_completed}/{experiment.progress_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function RateList({ metric }: { metric: Report["by_configuration"]["baseline"] }) {
  return (
    <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
      <div><dt className="text-muted">Attack success</dt><dd>{formatRate(metric.attack_success_rate)}</dd></div>
      <div><dt className="text-muted">Disclosure</dt><dd>{formatRate(metric.disclosure_rate)}</dd></div>
      <div><dt className="text-muted">Legitimate success</dt><dd>{formatRate(metric.legitimate_task_success_rate)}</dd></div>
      <div><dt className="text-muted">Average latency</dt><dd>{formatMs(metric.average_latency_ms)}</dd></div>
      <div><dt className="text-muted">Median latency</dt><dd>{formatMs(metric.median_latency_ms)}</dd></div>
      <div><dt className="text-muted">95th percentile</dt><dd>{formatMs(metric.p95_latency_ms)}</dd></div>
    </dl>
  );
}
