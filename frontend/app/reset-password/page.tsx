"use client";

import { Alert, Button, Field } from "@/components/ui";
import { createClient, isSupabaseConfigured } from "@/lib/supabase";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

export default function ResetPasswordPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [hasSession, setHasSession] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isSupabaseConfigured()) return;
    createClient().auth.getSession().then(({ data }) => setHasSession(Boolean(data.session)));
  }, []);

  async function requestReset(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const redirectTo = `${window.location.origin}/reset-password`;
    const { error: resetError } = await createClient().auth.resetPasswordForEmail(email, { redirectTo });
    setLoading(false);
    if (resetError) setError(resetError.message);
    else setMessage("If the account exists, a reset message has been sent.");
  }

  async function updatePassword(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const { error: updateError } = await createClient().auth.updateUser({ password });
    setLoading(false);
    if (updateError) setError(updateError.message);
    else setMessage("Password updated. You can sign in with the new password.");
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md space-y-4 rounded-2xl border border-line bg-card p-8">
        <h1 className="text-2xl font-semibold">Reset password</h1>
        {error && <Alert tone="bad">{error}</Alert>}
        {message && <Alert tone="good">{message}</Alert>}
        {hasSession ? (
          <form onSubmit={updatePassword} className="space-y-4">
            <Field label="New password">
              <input type="password" required minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} />
            </Field>
            <Button type="submit" disabled={loading}>Update password</Button>
          </form>
        ) : (
          <form onSubmit={requestReset} className="space-y-4">
            <Field label="Email">
              <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
            </Field>
            <Button type="submit" disabled={loading || !isSupabaseConfigured()}>Send reset link</Button>
          </form>
        )}
        <Link href="/login" className="block text-sm text-accent">Back to sign in</Link>
      </div>
    </main>
  );
}
