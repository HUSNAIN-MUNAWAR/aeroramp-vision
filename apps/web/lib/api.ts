export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiError = { error?: { code?: string; message?: string }; detail?: string | { message?: string } };

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("aeroramp_token");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    const data = (await response.json().catch(() => ({}))) as ApiError;
    const detail = typeof data.detail === "string" ? data.detail : data.error?.message ?? data.detail?.message ?? `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function login(email: string, password: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error("Invalid credentials");
  const data = (await response.json()) as { access_token: string };
  window.localStorage.setItem("aeroramp_token", data.access_token);
}

export function logout(): void {
  window.localStorage.removeItem("aeroramp_token");
  window.location.href = "/";
}
