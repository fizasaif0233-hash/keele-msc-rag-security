"use client";

import { Alert, Badge, Button, Card } from "@/components/ui";
import { api } from "@/lib/api";
import type { Experiment, Report } from "@/lib/types";
import { formatMs, formatRate, formatWhen } from "@/lib/utils";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

type Payload = {
  experiment: Experiment;
  report: Report;
  results: Array<{
    test_case_id: string;
    test_title: string;
    category: string;
    repetition_number: number;
    expected_outcome: string;
    actual_outcome: string;
    attack_success: boolean;
    information_disclosed: boolean;
    legitimate_task_success: boolean;
    response_latency_ms: number | null;
    error_message: string | null;
    evaluation_details: { manual_review?: boolean; decision_rule?: string; answer?: string | null };
  }>;
};

export default function ExperimentDetailPage() {
  const params = useParams<{ id: string }>();
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let timer = 0;
    let stopped = false;
    const load = () => {
      api<Payload>(`/api/v1/experiments/${params.id}/results`)
        .then((payload) => {
          if (stopped) return;
          setData(payload);
          if (payload.experiment.status === "running") timer = window.setTimeout(load, 2000);
        })
        .catch((reason: Error) => setError(reason.message));
    };
    load();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [params.id, tick]);

  async function restart() {
    await api(`/api/v1/experiments/${params.id}/start`, { method: "POST" });
    setTick((value) => value + 1);
  }

  if (error) return <Alert tone="bad">{error}</Alert>;
  if (!data) return <p className="text-muted">Loading experiment…</p>;
  const metric = data.report.by_configuration[data.experiment.configuration as "baseline" | "secured"];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/experiments" className="text-sm text-accent">All experiments</Link>
          <h2 className="mt-1 text-2xl font-semibold">{data.experiment.name}</h2>
          <p className="text-sm text-muted">{data.experiment.configuration} · started {formatWhen(data.experiment.started_at)}</p>
        </div>
        <Badge tone={data.experiment.status === "completed" ? "good" : data.experiment.status === "failed" ? "bad" : "warn"}>{data.experiment.status}</Badge>
      </header>
      {data.experiment.error_message && <Alert tone="warn">{data.experiment.error_message}</Alert>}
      <Card>
        <p className="text-sm text-muted">Progress</p>
        <p className="mt-1 text-2xl font-semibold">{data.experiment.progress_completed} / {data.experiment.progress_total}</p>
        <div className="mt-3 h-2 rounded-full bg-ink">
          <div
            className="h-2 rounded-full bg-accent"
            style={{ width: `${data.experiment.progress_total ? (data.experiment.progress_completed / data.experiment.progress_total) * 100 : 0}%` }}
          />
        </div>
        {data.experiment.status === "failed" && <Button className="mt-4" onClick={restart}>Resume failed run</Button>}
      </Card>
      {metric && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card><p className="text-sm text-muted">Attack success</p><p className="mt-2 text-xl">{formatRate(metric.attack_success_rate)}</p></Card>
          <Card><p className="text-sm text-muted">Disclosure</p><p className="mt-2 text-xl">{formatRate(metric.disclosure_rate)}</p></Card>
          <Card><p className="text-sm text-muted">Legitimate success</p><p className="mt-2 text-xl">{formatRate(metric.legitimate_task_success_rate)}</p></Card>
          <Card><p className="text-sm text-muted">Average latency</p><p className="mt-2 text-xl">{formatMs(metric.average_latency_ms)}</p></Card>
        </div>
      )}
      <Card className="overflow-auto">
        <table>
          <thead>
            <tr><th>Test</th><th>Category</th><th>Repetition</th><th>Outcome</th><th>Attack</th><th>Disclosure</th><th>Latency</th><th>Review</th></tr>
          </thead>
          <tbody>
            {data.results.map((result) => (
              <tr key={`${result.test_case_id}-${result.repetition_number}`}>
                <td>
                  {result.test_title}
                  <span className="mt-1 block text-xs text-muted">{result.evaluation_details.decision_rule}</span>
                </td>
                <td>{result.category}</td>
                <td>{result.repetition_number}</td>
                <td>{result.actual_outcome}</td>
                <td>{result.attack_success ? "yes" : "no"}</td>
                <td>{result.information_disclosed ? "yes" : "no"}</td>
                <td>{result.response_latency_ms ?? "—"}</td>
                <td>{result.evaluation_details.manual_review ? "manual" : ""}{result.error_message ? ` ${result.error_message}` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
