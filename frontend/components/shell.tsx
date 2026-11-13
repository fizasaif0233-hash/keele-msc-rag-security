"use client";

import { Alert } from "@/components/ui";
import { api } from "@/lib/api";
import { createClient, isSupabaseConfigured } from "@/lib/supabase";
import type { Profile, Role } from "@/lib/types";
import {
  BarChart3,
  FileText,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  MessagesSquare,
  ScrollText,
  Settings,
  Shield,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const NAV: Array<{ href: string; label: string; roles: Role[]; icon: typeof LayoutDashboard }> = [
  { href: "/dashboard", label: "Dashboard", roles: ["admin", "employee", "researcher"], icon: LayoutDashboard },
  { href: "/documents", label: "Documents", roles: ["admin", "employee", "researcher"], icon: FileText },
  { href: "/chat", label: "AI chat", roles: ["admin", "employee", "researcher"], icon: MessagesSquare },
  { href: "/research", label: "Security research", roles: ["admin", "researcher"], icon: Shield },
  { href: "/experiments", label: "Experiments", roles: ["admin", "researcher"], icon: FlaskConical },
  { href: "/analytics", label: "Evaluation", roles: ["admin", "researcher"], icon: BarChart3 },
  { href: "/logs", label: "Security logs", roles: ["admin", "researcher"], icon: ScrollText },
  { href: "/settings", label: "Settings", roles: ["admin", "researcher"], icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Profile>("/api/v1/me")
      .then(setProfile)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function signOut() {
    if (isSupabaseConfigured()) await createClient().auth.signOut();
    router.replace("/login");
  }

  const items = NAV.filter((item) => (profile ? item.roles.includes(profile.role) : false));

  return (
    <div className="min-h-screen md:grid md:grid-cols-[16rem_1fr]">
      <aside className="border-b border-line bg-panel md:border-b-0 md:border-r">
        <div className="px-4 py-5">
          <p className="text-xs uppercase tracking-[0.16em] text-accent">MSc research platform</p>
          <h1 className="mt-1 text-lg font-semibold leading-snug">RAG security evaluation</h1>
          {profile && (
            <p className="mt-3 text-sm text-muted">
              {profile.email}
              <span className="mt-1 block capitalize text-violet">{profile.role}</span>
            </p>
          )}
        </div>
        <nav className="flex gap-2 overflow-auto px-3 pb-3 md:block md:space-y-1 md:px-3 md:pb-6">
          {items.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm ${
                  active ? "bg-white/10 text-white" : "text-muted hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="hidden px-3 pb-5 md:block">
          <button onClick={signOut} className="flex items-center gap-2 px-3 py-2 text-sm text-muted hover:text-white">
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>
      <div>
        <div className="flex justify-end border-b border-line px-4 py-3 md:hidden">
          <button onClick={signOut} className="text-sm text-muted">
            Sign out
          </button>
        </div>
        <main className="mx-auto max-w-6xl px-4 py-6 md:px-8">
          {error && (
            <div className="mb-4">
              <Alert tone="bad">{error}</Alert>
            </div>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
