"use client";

import { Alert, Badge, Button, Card, EmptyState, Field } from "@/components/ui";
import { api } from "@/lib/api";
import type { TestCaseRecord } from "@/lib/types";
import { FormEvent, useEffect, useState } from "react";

const CATEGORIES = [
  "benign",
  "direct_prompt_injection",
  "indirect_prompt_injection",
  "unauthorised_disclosure",
  "input_validation",
];

type Dataset = { id: string; name: string; description: string; case_count: number };

export default function ResearchPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [cases, setCases] = useState<TestCaseRecord[]>([]);
  const [category, setCategory] = useState("all");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function loadDatasets() {
    const response = await api<{ datasets: Dataset[] }>("/api/v1/datasets");
    setDatasets(response.datasets);
    return response.datasets;
  }

  async function loadCases(id: string) {
    const response = await api<{ cases: TestCaseRecord[] }>(`/api/v1/datasets/${id}/cases`);
    setCases(response.cases);
  }

  useEffect(() => {
    loadDatasets()
      .then((rows) => {
        if (rows[0]) {
          setDatasetId(rows[0].id);
          return loadCases(rows[0].id);
        }
        return undefined;
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function createDataset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/api/v1/datasets", {
        method: "POST",
        body: JSON.stringify({ name: form.get("name"), description: form.get("description") }),
      });
      setMessage("Dataset created.");
      event.currentTarget.reset();
      await loadDatasets();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create the dataset.");
    }
  }

  async function createCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    let criteria: Record<string, unknown> = { is_attack: form.get("category") !== "benign", actor_role: "employee" };
    const raw = String(form.get("criteria") || "").trim();
    if (raw) {
      try {
        criteria = JSON.parse(raw) as Record<string, unknown>;
      } catch {
        setError("Evaluation criteria must be valid JSON.");
        return;
      }
    }
    try {
      await api(`/api/v1/datasets/${datasetId}/cases`, {
        method: "POST",
        body: JSON.stringify({
          category: form.get("category"),
          title: form.get("title"),
          description: form.get("description"),
          input: form.get("input"),
          expected_outcome: form.get("expected_outcome"),
          evaluation_criteria: criteria,
        }),
      });
      setMessage("Test case saved.");
      event.currentTarget.reset();
      await loadCases(datasetId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save the test case.");
    }
  }

  const visible = cases.filter((item) => category === "all" || item.category === category);

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold">Security research</h2>
        <p className="mt-1 text-sm text-muted">Official cases are seeded. New cases need explicit evaluation criteria. HTTP status is not an outcome.</p>
      </header>
      {error && <Alert tone="bad">{error}</Alert>}
      {message && <Alert tone="good">{message}</Alert>}
      <Card>
        <form onSubmit={createDataset} className="grid gap-3 md:grid-cols-[1fr_2fr_auto]">
          <Field label="New dataset name"><input name="name" required minLength={3} /></Field>
          <Field label="Description"><input name="description" /></Field>
          <div className="flex items-end"><Button type="submit">Create dataset</Button></div>
        </form>
      </Card>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Dataset">
          <select value={datasetId} onChange={(event) => { setDatasetId(event.target.value); loadCases(event.target.value).catch((reason: Error) => setError(reason.message)); }}>
            {datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.name} ({dataset.case_count})</option>)}
          </select>
        </Field>
        <Field label="Category">
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="all">All categories</option>
            {CATEGORIES.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
          </select>
        </Field>
      </div>
      {visible.length === 0 ? (
        <EmptyState title="No test cases in this view" body="Seed the synthetic dataset or add a case with evaluation criteria." />
      ) : (
        <div className="space-y-3">
          {visible.map((item) => (
            <Card key={item.id}>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-semibold">{item.title}</h3>
                <Badge>{item.category.replaceAll("_", " ")}</Badge>
              </div>
              <p className="mt-2 text-sm text-muted">{item.description}</p>
              <p className="mt-3 text-sm"><span className="text-muted">Input. </span>{item.input.slice(0, 500)}</p>
              <p className="mt-2 text-sm"><span className="text-muted">Expected. </span>{item.expected_outcome}</p>
            </Card>
          ))}
        </div>
      )}
      <Card>
        <h3 className="font-semibold">Add a test case</h3>
        <form onSubmit={createCase} className="mt-4 grid gap-3">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Title"><input name="title" required minLength={3} /></Field>
            <Field label="Category">
              <select name="category" defaultValue="benign">{CATEGORIES.map((item) => <option key={item} value={item}>{item}</option>)}</select>
            </Field>
          </div>
          <Field label="Description"><input name="description" /></Field>
          <Field label="Input"><textarea name="input" required /></Field>
          <Field label="Expected outcome"><textarea name="expected_outcome" required /></Field>
          <Field label="Evaluation criteria JSON">
            <textarea name="criteria" placeholder='{"is_attack": false, "actor_role": "employee", "answer_should_contain": ["09:00"]}' />
          </Field>
          <Button type="submit" disabled={!datasetId}>Save test case</Button>
        </form>
      </Card>
    </div>
  );
}
