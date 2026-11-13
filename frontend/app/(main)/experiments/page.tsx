"use client";

import { Alert, Badge, Button, Card, EmptyState, Field } from "@/components/ui";
import { api } from "@/lib/api";
import type { Experiment } from "@/lib/types";
import { formatWhen } from "@/lib/utils";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

type Dataset = { id: string; name: string; case_count: number };

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function reload() {
    const response = await api<{ experiments: Experiment[] }>("/api/v1/experiments");
    setExperiments(response.experiments);
  }

  useEffect(() => {
    Promise.all([reload(), api<{ datasets: Dataset[] }>("/api/v1/datasets").then((response) => setDatasets(response.datasets))])
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const configurations = ["baseline", "secured"].filter((name) => form.get(name) === "on");
    if (configurations.length === 0) {
      setError("Select at least one configuration.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await api("/api/v1/experiments", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          configurations,
          dataset_id: form.get("dataset_id"),
          repetitions: Number(form.get("repetitions") || 1),
          top_k: form.get("top_k") ? Number(form.get("top_k")) : null,
          similarity_threshold: form.get("similarity_threshold") ? Number(form.get("similarity_threshold")) : null,
          temperature: form.get("temperature") ? Number(form.get("temperature")) : null,
        }),
      });
      setMessage("Experiment started. Open the run to watch progress.");
      await reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The experiment could not start.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold">Experiments</h2>
        <p className="mt-1 text-sm text-muted">A paired run uses the same dataset, repetitions, model, and retrieval settings. Only the selected security configuration changes.</p>
      </header>
      {error && <Alert tone="bad">{error}</Alert>}
      {message && <Alert tone="good">{message}</Alert>}
      <Card>
        <form onSubmit={create} className="grid gap-4 md:grid-cols-2">
          <Field label="Name"><input name="name" required minLength={3} /></Field>
          <Field label="Dataset">
            <select name="dataset_id" required>
              {datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.name}</option>)}
            </select>
          </Field>
          <Field label="Repetitions"><input name="repetitions" type="number" min={1} max={20} defaultValue={1} /></Field>
          <Field label="Temperature"><input name="temperature" type="number" min={0} max={1} step="0.1" placeholder="Use saved setting" /></Field>
          <Field label="Top-k"><input name="top_k" type="number" min={1} max={20} placeholder="Use saved setting" /></Field>
          <Field label="Similarity threshold"><input name="similarity_threshold" type="number" min={-1} max={1} step="0.05" placeholder="Use saved setting" /></Field>
          <label className="flex items-center gap-2"><input className="w-auto" type="checkbox" name="baseline" defaultChecked /> Baseline configuration</label>
          <label className="flex items-center gap-2"><input className="w-auto" type="checkbox" name="secured" defaultChecked /> Secured configuration</label>
          <div><Button type="submit" disabled={loading || datasets.length === 0}>{loading ? "Starting…" : "Start experiment"}</Button></div>
        </form>
      </Card>
      {experiments.length === 0 ? (
        <EmptyState title="No experiments yet" body="Create a run after the dataset and model credentials are configured." />
      ) : (
        <Card className="overflow-auto">
          <table>
            <thead><tr><th>Name</th><th>Configuration</th><th>Status</th><th>Progress</th><th>Started</th></tr></thead>
            <tbody>
              {experiments.map((experiment) => (
                <tr key={experiment.id}>
                  <td><Link className="text-accent" href={`/experiments/${experiment.id}`}>{experiment.name}</Link></td>
                  <td>{experiment.configuration}</td>
                  <td><Badge tone={experiment.status === "completed" ? "good" : experiment.status === "failed" ? "bad" : "warn"}>{experiment.status}</Badge></td>
                  <td>{experiment.progress_completed}/{experiment.progress_total}</td>
                  <td>{formatWhen(experiment.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
