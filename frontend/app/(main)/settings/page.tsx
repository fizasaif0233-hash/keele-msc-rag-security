"use client";

import { Alert, Badge, Button, Card, Field } from "@/components/ui";
import { api } from "@/lib/api";
import { FormEvent, useEffect, useState } from "react";

type SettingsResponse = {
  can_edit: boolean;
  settings: Record<string, string | number | boolean>;
  environment: Record<string, string | number | boolean>;
};

const EDITABLE = [
  "llm_model",
  "embedding_model",
  "chunk_size",
  "chunk_overlap",
  "top_k",
  "similarity_threshold",
  "temperature",
  "max_input_chars_secured",
  "max_input_chars_baseline",
  "max_upload_bytes",
  "rate_limit_per_minute",
  "allow_employee_upload",
];

export default function SettingsPage() {
  const [data, setData] = useState<SettingsResponse | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<SettingsResponse>("/api/v1/settings")
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!data) return;
    const form = new FormData(event.currentTarget);
    const values: Record<string, string | number | boolean> = {};
    EDITABLE.forEach((key) => {
      const raw = form.get(key);
      if (raw === null) return;
      if (key === "allow_employee_upload") values[key] = raw === "true";
      else if (["llm_model", "embedding_model"].includes(key)) values[key] = String(raw);
      else values[key] = Number(raw);
    });
    try {
      const updated = await api<SettingsResponse>("/api/v1/settings", { method: "PUT", body: JSON.stringify({ values }) });
      setData(updated);
      setMessage("Settings saved. Secrets remain in the server environment.");
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Settings could not be saved.");
    }
  }

  if (error && !data) return <Alert tone="bad">{error}</Alert>;
  if (!data) return <p className="text-muted">Loading settings…</p>;

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold">Settings</h2>
        <p className="mt-1 text-sm text-muted">Model names and retrieval settings can be changed here. API keys and database passwords stay on the server.</p>
      </header>
      {error && <Alert tone="bad">{error}</Alert>}
      {message && <Alert tone="good">{message}</Alert>}
      <Card>
        <h3 className="font-semibold">Environment status</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {Object.entries(data.environment).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between gap-3 text-sm">
              <span>{key.replaceAll("_", " ")}</span>
              {typeof value === "boolean" ? <Badge tone={value ? "good" : "bad"}>{value ? "Configured" : "Missing"}</Badge> : <span>{String(value)}</span>}
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <form onSubmit={save} className="grid gap-4 md:grid-cols-2">
          {EDITABLE.map((key) => (
            <Field key={key} label={key.replaceAll("_", " ")}>
              {key === "allow_employee_upload" ? (
                <select name={key} defaultValue={String(data.settings[key])} disabled={!data.can_edit}>
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              ) : (
                <input name={key} defaultValue={String(data.settings[key] ?? "")} disabled={!data.can_edit} />
              )}
            </Field>
          ))}
          {data.can_edit && <div className="md:col-span-2"><Button type="submit">Save settings</Button></div>}
        </form>
      </Card>
    </div>
  );
}
