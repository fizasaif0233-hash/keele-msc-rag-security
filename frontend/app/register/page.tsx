"use client";

import { Alert, Button, Field } from "@/components/ui";
import { createClient, isSupabaseConfigured } from "@/lib/supabase";
import Link from "next/link";
import { FormEvent, useState } from "react";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("The passwords do not match.");
      return;
    }
    if (password.length < 12) {
      setError("Use a password of at least 12 characters.");
      return;
    }
    setLoading(true);
    setError("");
    const { error: signUpError } = await createClient().auth.signUp({ email, password });
    setLoading(false);
    if (signUpError) {
      setError(signUpError.message);
      return;
    }
    setMessage("Account created. If email confirmation is enabled, confirm the message from Supabase before signing in. New accounts start as employees.");
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={onSubmit} className="w-full max-w-md space-y-4 rounded-2xl border border-line bg-card p-8">
        <h1 className="text-2xl font-semibold">Create an account</h1>
        <p className="text-sm text-muted">Registration does not grant an administrator role. Promote the first administrator with the server script.</p>
        {!isSupabaseConfigured() && <Alert tone="bad">Supabase is not configured in this frontend.</Alert>}
        {error && <Alert tone="bad">{error}</Alert>}
        {message && <Alert tone="good">{message}</Alert>}
        <Field label="Email">
          <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </Field>
        <Field label="Password">
          <input type="password" required value={password} onChange={(event) => setPassword(event.target.value)} />
        </Field>
        <Field label="Confirm password">
          <input type="password" required value={confirm} onChange={(event) => setConfirm(event.target.value)} />
        </Field>
        <Button type="submit" disabled={loading || !isSupabaseConfigured()} className="w-full">
          {loading ? "Creating account…" : "Register"}
        </Button>
        <Link href="/login" className="text-sm text-accent">Back to sign in</Link>
      </form>
    </main>
  );
}
