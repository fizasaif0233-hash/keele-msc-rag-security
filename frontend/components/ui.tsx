import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({
  className,
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" }) {
  const styles = {
    primary: "bg-accent text-ink hover:bg-[#9ab6ff]",
    ghost: "border border-line bg-transparent text-slate-100 hover:bg-white/5",
    danger: "bg-rose-900/80 text-rose-50 hover:bg-rose-800",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-lg px-3.5 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60",
        styles[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cn("rounded-2xl border border-line bg-card p-5", className)}>{children}</section>;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "bad" | "warn" }) {
  const tones = {
    neutral: "bg-white/5 text-slate-200",
    good: "bg-emerald-950 text-emerald-200",
    bad: "bg-rose-950 text-rose-200",
    warn: "bg-amber-950 text-amber-100",
  };
  return <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-medium", tones[tone])}>{children}</span>;
}

export function Alert({ children, tone = "warn" }: { children: ReactNode; tone?: "warn" | "bad" | "good" }) {
  const tones = {
    warn: "border-amber-800/70 bg-amber-950/40 text-amber-50",
    bad: "border-rose-900 bg-rose-950/50 text-rose-50",
    good: "border-emerald-900 bg-emerald-950/40 text-emerald-50",
  };
  return <div className={cn("rounded-xl border px-3 py-2 text-sm", tones[tone])}>{children}</div>;
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-dashed border-line px-4 py-8 text-center">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted">{body}</p>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label>{label}</label>
      {children}
    </div>
  );
}
