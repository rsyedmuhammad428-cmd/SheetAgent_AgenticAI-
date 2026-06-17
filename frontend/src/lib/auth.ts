/**
 * auth.ts — Authentication API client
 * Connects to FastAPI backend auth endpoints (backend/app/api/routes/auth.py).
 *
 * Backend endpoints:
 *   POST /api/auth/register   → { access_token, token_type, user }
 *   POST /api/auth/login      → { access_token, token_type, user }
 *   GET  /api/auth/me         → { id, email, full_name, created_at }
 *   POST /api/auth/logout     → { message }
 */

export const API_BASE = "";

export interface User {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

const TOKEN_KEY = "sheetagent_token";
const USER_KEY  = "sheetagent_user";

// ── Token helpers ─────────────────────────────────────────────────────────────

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function saveAuth(res: AuthResponse) {
  localStorage.setItem(TOKEN_KEY, res.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(res.user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getSavedUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

// ── Auth headers for other API calls ─────────────────────────────────────────

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── API calls ─────────────────────────────────────────────────────────────────

async function authFetch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || data.message || `Error ${res.status}`);
  }
  return data as T;
}

export async function register(
  fullName: string,
  email: string,
  password: string,
): Promise<AuthResponse> {
  const res = await authFetch<AuthResponse>("/api/auth/register", {
    full_name: fullName,
    email,
    password,
  });
  saveAuth(res);
  return res;
}

export async function login(
  email: string,
  password: string,
): Promise<AuthResponse> {
  const res = await authFetch<AuthResponse>("/api/auth/login", {
    email,
    password,
  });
  saveAuth(res);
  return res;
}

export async function logout(): Promise<void> {
  const token = getToken();
  if (token) {
    await fetch(`${API_BASE}/api/auth/logout`, {
      method:  "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }
  clearAuth();
}

export async function getMe(): Promise<User> {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}
