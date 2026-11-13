"use client";

import { Alert, Badge, Card, EmptyState, Field } from "@/components/ui";
import { api } from "@/lib/api";
import type { SecurityEvent } from "@/lib/types";
import { formatWhen } from "@/lib/utils";
import { useEffect, useState } from "react";

export default function LogsPage() {
  const [logs, setLogs] = useState<SecurityEvent[]>([]);
  const [eventType, setEventType] = useState("");
  const [configuration, setConfiguration] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (eventType) params.set("event_type", eventType);
    if (configuration) params.set("configuration", configuration);
    api<{ logs: SecurityEvent[] }>(`/api/v1/security-logs?${params.toString()}`)
      .then((response) => setLogs(response.logs))
      .catch((reason: Error) => setError(reason.message));
  }, [eventType, configuration]);

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold">Security logs</h2>
        <p className="mt-1 text-sm text-muted">Logs record decisions and identifiers. They do not store passwords, tokens, or full document text.</p>
      </header>
      {error && <Alert tone="bad">{error}</Alert>}
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Event category">
          <input value={eventType} onChange={(event) => setEventType(event.target.value)} placeholder="authorisation_failure" />
        </Field>
        <Field label="Configuration">
          <select value={configuration} onChange={(event) => setConfiguration(event.target.value)}>
            <option value="">All</option>
            <option value="baseline">Baseline</option>
            <option value="secured">Secured</option>
          </select>
        </Field>
      </div>
      {logs.length === 0 ? (
        <EmptyState title="No matching log records" body="Security events appear after authentication failures, blocked access, suspicious requests, or disclosure checks." />
      ) : (
        <Card className="overflow-auto">
          <table>
            <thead>
              <tr><th>Time</th><th>User</th><th>Event</th><th>Configuration</th><th>Outcome</th><th>Severity</th><th>Related ID</th></tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td>{formatWhen(log.created_at)}</td>
                  <td>{log.user_email || "Unknown"}</td>
                  <td>{log.event_type}</td>
                  <td>{log.configuration || "—"}</td>
                  <td>{log.outcome}</td>
                  <td><Badge tone={log.severity === "high" ? "bad" : log.severity === "medium" ? "warn" : "neutral"}>{log.severity}</Badge></td>
                  <td className="text-xs text-muted">{log.experiment_id || log.test_case_id || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
