// RegLens API client. The frontend talks to the backend ONLY over this
// REST client, with the base URL from VITE_API_URL (default localhost:8000).
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function token(): string | null {
  return localStorage.getItem("reglens_token");
}
export function setToken(t: string | null) {
  if (t) localStorage.setItem("reglens_token", t);
  else localStorage.removeItem("reglens_token");
}

export async function api(path: string, opts: RequestInit = {}): Promise<any> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string> || {}) };
  const t = token();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  if (opts.body && typeof opts.body === "string" && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_URL}${path}`, { ...opts, headers });
  if (res.status === 401) {
    setToken(null);
    throw new Error("Session expired — please sign in again.");
  }
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    throw new Error((data && (data.detail || data.message)) || `Request failed (${res.status})`);
  }
  return data;
}

export async function apiBlob(path: string, opts: RequestInit = {}): Promise<Blob> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string> || {}) };
  const t = token();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  if (opts.body && typeof opts.body === "string") headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_URL}${path}`, { ...opts, headers });
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.blob();
}

export const API_BASE = API_URL;
