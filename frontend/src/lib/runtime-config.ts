const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");

const publicApiBase = trimTrailingSlash(
  (import.meta.env.VITE_API_BASE_URL ?? "").trim(),
);

export const API_BASE = publicApiBase;

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return API_BASE ? `${API_BASE}${normalizedPath}` : normalizedPath;
}

export function buildWebSocketUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (API_BASE) {
    return `${API_BASE.replace(/^http/i, "ws")}${normalizedPath}`;
  }

  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${normalizedPath}`;
  }

  return normalizedPath;
}
