import { createClient, isSupabaseConfigured } from "@/lib/supabase";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function messageFromBody(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object" || !("detail" in body)) return fallback;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) return String((item as { msg: unknown }).msg);
        return String(item);
      })
      .join(" ");
  }
  return fallback;
}

async function authorisedHeaders(init: RequestInit): Promise<Headers> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (!isSupabaseConfigured()) return headers;
  const { data } = await createClient().auth.getSession();
  const token = data.session?.access_token;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: await authorisedHeaders(init),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = messageFromBody(await response.json(), detail);
    } catch {
      detail = response.statusText;
    }
    throw new ApiError(detail || "The request failed.", response.status);
  }
  return (await response.json()) as T;
}

export async function apiBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_URL}${path}`, { headers: await authorisedHeaders({}) });
  if (!response.ok) {
    throw new ApiError("The export could not be downloaded.", response.status);
  }
  return response.blob();
}
