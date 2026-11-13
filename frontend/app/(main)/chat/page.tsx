"use client";

import { Alert, Badge, Button, Card, Field } from "@/components/ui";
import { api } from "@/lib/api";
import type { DocumentRecord, Profile } from "@/lib/types";
import { FormEvent, useEffect, useState } from "react";

type Session = { id: string; title: string; configuration: string };
type Message = {
  id: string;
  role: string;
  content: string;
  latency_ms: number | null;
  metadata: {
    sources?: Array<{ title: string; similarity: number; access_level: string; excerpt: string }>;
    warnings?: string[];
    configuration?: string;
  };
};

export default function ChatPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [active, setActive] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [configuration, setConfiguration] = useState("secured");
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);

  async function loadSessions() {
    const response = await api<{ sessions: Session[] }>("/api/v1/chat/sessions");
    setSessions(response.sessions);
    return response.sessions;
  }

  async function loadMessages(sessionId: string) {
    const response = await api<{ messages: Message[] }>(`/api/v1/chat/sessions/${sessionId}/messages`);
    setMessages(response.messages);
  }

  useEffect(() => {
    Promise.all([
      api<Profile>("/api/v1/me"),
      api<{ documents: DocumentRecord[] }>("/api/v1/documents"),
      loadSessions(),
    ]).then(([me, docs, existing]) => {
      setProfile(me);
      setDocuments(docs.documents.filter((item) => item.processing_status === "ready"));
      if (me.role === "employee") setConfiguration("secured");
      if (existing[0]) {
        setActive(existing[0].id);
        setConfiguration(me.role === "employee" ? "secured" : existing[0].configuration);
        return loadMessages(existing[0].id);
      }
      return undefined;
    }).catch((reason: Error) => setError(reason.message));
  }, []);

  async function createSession() {
    const session = await api<Session>("/api/v1/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ title: "New chat", configuration: profile?.role === "employee" ? "secured" : configuration }),
    });
    setActive(session.id);
    setMessages([]);
    await loadSessions();
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!active) {
      setError("Create a chat session first.");
      return;
    }
    setSending(true);
    setError("");
    try {
      await api(`/api/v1/chat/sessions/${active}/messages`, {
        method: "POST",
        body: JSON.stringify({
          content: question,
          configuration,
          document_ids: selectedDocs.length ? selectedDocs : null,
        }),
      });
      setQuestion("");
      await loadMessages(active);
      await loadSessions();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The question could not be sent.");
      if (active) await loadMessages(active);
    } finally {
      setSending(false);
    }
  }

  const canUseBaseline = profile?.role === "admin" || profile?.role === "researcher";

  return (
    <div className="grid gap-4 lg:grid-cols-[16rem_1fr]">
      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Chats</h2>
          <Button onClick={createSession}>New</Button>
        </div>
        {sessions.map((session) => (
          <button
            key={session.id}
            onClick={() => { setActive(session.id); loadMessages(session.id).catch((reason: Error) => setError(reason.message)); }}
            className={`block w-full rounded-lg px-3 py-2 text-left text-sm ${active === session.id ? "bg-white/10" : "hover:bg-white/5"}`}
          >
            <span className="block truncate">{session.title}</span>
            <span className="text-xs text-muted">{session.configuration}</span>
          </button>
        ))}
      </Card>
      <div className="space-y-4">
        <Card className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-xl font-semibold">AI chat</h2>
            <Badge tone={configuration === "secured" ? "good" : "warn"}>{configuration}</Badge>
          </div>
          {error && <Alert tone="bad">{error}</Alert>}
          {!canUseBaseline && <Alert>Employees use the secured configuration. Baseline runs are started by researchers.</Alert>}
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Configuration">
              <select value={configuration} disabled={!canUseBaseline} onChange={(event) => setConfiguration(event.target.value)}>
                <option value="secured">Secured</option>
                {canUseBaseline && <option value="baseline">Baseline</option>}
              </select>
            </Field>
            <fieldset>
              <legend className="mb-2 text-sm text-slate-200">Document scope</legend>
              <div className="max-h-36 space-y-1 overflow-auto rounded-xl border border-line p-3 text-sm">
                {documents.length === 0 && <p className="text-muted">No ready documents are visible to this account.</p>}
                {documents.map((document) => (
                  <label key={document.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      className="w-auto"
                      checked={selectedDocs.includes(document.id)}
                      onChange={(event) => {
                        setSelectedDocs((current) => event.target.checked ? [...current, document.id] : current.filter((id) => id !== document.id));
                      }}
                    />
                    {document.title}
                  </label>
                ))}
              </div>
              <p className="mt-1 text-xs text-muted">Leave this empty to use the configuration default. Secured searches authorised documents. Baseline searches the ready corpus.</p>
            </fieldset>
          </div>
        </Card>
        <Card className="space-y-4">
          {messages.length === 0 && <p className="text-sm text-muted">Ask a question about the synthetic corpus.</p>}
          {messages.map((message) => (
            <article key={message.id} className="rounded-xl border border-line bg-ink/60 p-4">
              <div className="mb-2 flex items-center justify-between text-xs text-muted">
                <span>{message.role}</span>
                <span>{message.metadata.configuration || ""} {message.latency_ms != null ? `· ${message.latency_ms} ms` : ""}</span>
              </div>
              <p className="whitespace-pre-wrap text-sm">{message.content}</p>
              {message.metadata.warnings?.map((warning) => <p key={warning} className="mt-2 text-sm text-amber-100">{warning}</p>)}
              {message.metadata.sources && message.metadata.sources.length > 0 && (
                <ul className="mt-3 space-y-2 text-xs text-muted">
                  {message.metadata.sources.map((source, index) => (
                    <li key={`${source.title}-${index}`}>
                      {source.title} · {source.access_level} · similarity {source.similarity}
                      <span className="mt-1 block text-slate-300">{source.excerpt}</span>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
          <form onSubmit={send} className="space-y-3">
            <Field label="Question">
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} required />
            </Field>
            <Button type="submit" disabled={sending || !active}>{sending ? "Waiting for the model…" : "Ask"}</Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
