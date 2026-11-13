"use client";

import { Alert, Button, Field } from "@/components/ui";
import { createClient, isSupabaseConfigured } from "@/lib/supabase";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const configured = isSupabaseConfigured();

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const { error: signInError } = await createClient().auth.signInWithPassword({ email, password });
    setLoading(false);
    if (signInError) {
      setError(signInError.message);
      return;
    }
    router.replace("/dashboard");
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={onSubmit} className="w-full max-w-md space-y-4 rounded-2xl border border-line bg-card p-8">
        <p className="text-sm text-accent">RAG security evaluation</p>
        <h1 className="text-2xl font-semibold">Sign in</h1>
        <p className="text-sm text-muted">Use the account you registered. Roles are assigned on the server.</p>
        {!configured && <Alert tone="bad">Add the Supabase URL and anon key to frontend/.env.local before signing in.</Alert>}
        {error && <Alert tone="bad">{error}</Alert>}
        <Field label="Email">
          <input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </Field>
        <Field label="Password">
          <input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
        </Field>
        <Button type="submit" disabled={loading || !configured} className="w-full">
          {loading ? "Signing in…" : "Sign in"}
        </Button>
        <p className="text-sm text-muted">
          <Link href="/register" className="text-accent">Create an account</Link>
          {" · "}
          <Link href="/reset-password" className="text-accent">Reset password</Link>
        </p>
      </form>
    </main>
  );
}
