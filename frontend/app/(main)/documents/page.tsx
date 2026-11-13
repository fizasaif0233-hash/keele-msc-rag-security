"use client";

import { Alert, Badge, Button, Card, EmptyState, Field } from "@/components/ui";
import { api } from "@/lib/api";
import type { DocumentRecord, Profile } from "@/lib/types";
import { formatWhen } from "@/lib/utils";
import { FormEvent, useEffect, useState } from "react";

const ACCESS = [
  { value: "public", label: "Public" },
  { value: "employee", label: "Employee" },
  { value: "hr", label: "HR" },
  { value: "confidential", label: "Confidential" },
  { value: "admin", label: "Administrator" },
];

export default function DocumentsPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selected, setSelected] = useState<DocumentRecord | null>(null);
  const [permissions, setPermissions] = useState<Array<{ id: string; email: string | null; permission: string }>>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");

  async function reload() {
    const response = await api<{ documents: DocumentRecord[] }>("/api/v1/documents");
    setDocuments(response.documents);
  }

  useEffect(() => {
    api<Profile>("/api/v1/me").then(setProfile).catch((reason: Error) => setError(reason.message));
    reload().catch((reason: Error) => setError(reason.message));
  }, []);

  async function openDocument(id: string) {
    setError("");
    const document = await api<DocumentRecord>(`/api/v1/documents/${id}`);
    setSelected(document);
    if (profile?.role === "admin") {
      const grants = await api<{ permissions: Array<{ id: string; email: string | null; permission: string }> }>(
        `/api/v1/documents/${id}/permissions`,
      );
      setPermissions(grants.permissions);
    }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const created = await api<DocumentRecord>("/api/v1/documents", { method: "POST", body: data });
      setMessage(`${created.title} is ${created.processing_status}.`);
      form.reset();
      await reload();
      setSelected(created);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed.");
    } finally {
      setLoading(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Delete this document and its chunks?")) return;
    await api(`/api/v1/documents/${id}`, { method: "DELETE" });
    setSelected(null);
    await reload();
  }

  async function changeAccess(accessLevel: string) {
    if (!selected) return;
    await api(`/api/v1/documents/${selected.id}/access`, {
      method: "PUT",
      body: JSON.stringify({ access_level: accessLevel }),
    });
    await openDocument(selected.id);
    await reload();
  }

  async function grant(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await api(`/api/v1/documents/${selected.id}/permissions`, {
      method: "POST",
      body: JSON.stringify({ email, permission: "read" }),
    });
    setEmail("");
    await openDocument(selected.id);
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold">Documents</h2>
        <p className="mt-1 text-sm text-muted">Uploads accept PDF and TXT files. Access changes are enforced on the server.</p>
      </header>
      {error && <Alert tone="bad">{error}</Alert>}
      {message && <Alert tone="good">{message}</Alert>}
      {profile && profile.can_upload === false && (
        <Alert>This account cannot upload documents. An administrator can allow employee uploads in settings.</Alert>
      )}
      {profile?.can_upload !== false && <Card>
        <form onSubmit={upload} className="grid gap-4 md:grid-cols-4">
          <Field label="Title">
            <input name="title" placeholder="Optional title" />
          </Field>
          <Field label="Access level">
            <select name="access_level" defaultValue="employee">
              {(profile?.role === "admin" ? ACCESS : ACCESS.filter((level) => level.value === "public" || level.value === "employee")).map((level) => (
                <option key={level.value} value={level.value}>{level.label}</option>
              ))}
            </select>
          </Field>
          <Field label="File">
            <input name="file" type="file" accept=".pdf,.txt,application/pdf,text/plain" required />
          </Field>
          <div className="flex items-end">
            <Button type="submit" disabled={loading}>{loading ? "Uploading…" : "Upload"}</Button>
          </div>
        </form>
      </Card>}
      {documents.length === 0 ? (
        <EmptyState title="No documents yet" body="Upload a text or PDF file, or run the seed script to load the synthetic corpus." />
      ) : (
        <Card className="overflow-auto">
          <table>
            <thead>
              <tr>
                <th>Title</th><th>Owner</th><th>Access</th><th>Status</th><th>Chunks</th><th>Created</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => (
                <tr key={document.id} className="cursor-pointer hover:bg-white/5" onClick={() => openDocument(document.id)}>
                  <td>{document.title}</td>
                  <td>{document.owner_email}</td>
                  <td>{ACCESS.find((level) => level.value === document.access_level)?.label ?? document.access_level}</td>
                  <td><Badge tone={document.processing_status === "ready" ? "good" : document.processing_status === "failed" ? "bad" : "warn"}>{document.processing_status}</Badge></td>
                  <td>{document.chunk_count}</td>
                  <td>{formatWhen(document.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {selected && (
        <Card className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-lg font-semibold">{selected.title}</h3>
            <div className="flex gap-2">
              {(profile?.role === "admin" || profile?.role === "researcher" || profile?.id === selected.owner_id) && (
                <Button variant="ghost" onClick={() => api(`/api/v1/documents/${selected.id}/reprocess`, { method: "POST" }).then(() => openDocument(selected.id)).catch((reason: Error) => setError(reason.message))}>Reprocess</Button>
              )}
              {(profile?.role === "admin" || profile?.id === selected.owner_id) && (
                <Button variant="danger" onClick={() => remove(selected.id).catch((reason: Error) => setError(reason.message))}>Delete</Button>
              )}
            </div>
          </div>
          <p className="text-sm text-muted">Owner {selected.owner_email} · {selected.chunk_count} chunks · markers: {selected.protected_markers.join(", ") || "none"}</p>
          {selected.error_message && <Alert tone="warn">{selected.error_message}</Alert>}
          {profile?.role === "admin" && (
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Access level">
                <select value={selected.access_level} onChange={(event) => changeAccess(event.target.value)}>
                  {ACCESS.map((level) => <option key={level.value} value={level.value}>{level.label}</option>)}
                </select>
              </Field>
              <form onSubmit={grant} className="space-y-2">
                <Field label="Grant read access by email">
                  <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="person@example.com" />
                </Field>
                <Button type="submit">Grant</Button>
              </form>
            </div>
          )}
          {profile?.role === "admin" && permissions.length > 0 && (
            <ul className="text-sm">
              {permissions.map((permission) => (
                <li key={permission.id} className="flex items-center justify-between border-b border-line py-2">
                  <span>{permission.email} · {permission.permission}</span>
                  <button className="text-rose-200" onClick={() => api(`/api/v1/documents/${selected.id}/permissions/${permission.id}`, { method: "DELETE" }).then(() => openDocument(selected.id))}>Revoke</button>
                </li>
              ))}
            </ul>
          )}
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-ink p-4 text-sm">{selected.extracted_text || "No extracted text."}</pre>
        </Card>
      )}
    </div>
  );
}
