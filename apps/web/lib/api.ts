export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

export type UserRole = "viewer" | "analyst" | "admin";

export function getStoredRole(): UserRole {
  if (typeof window === "undefined") return "admin";
  const r = window.localStorage.getItem("mt_role");
  if (r === "viewer" || r === "analyst" || r === "admin") return r;
  return "admin";
}

export function setStoredRole(role: UserRole): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem("mt_role", role);
  }
}

export async function apiFetch<T = any>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const role = getStoredRole();
  const headers = new Headers(init?.headers || {});
  headers.set("X-Role", role);
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      msg = errBody.detail || JSON.stringify(errBody);
    } catch {
      msg = await res.text();
    }
    throw new Error(msg);
  }
  return res.json();
}

