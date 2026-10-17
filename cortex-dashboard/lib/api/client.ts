/**
 * Base API client for CortexOS backend.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let _apiKey: string | null = null;

export function setApiKey(key: string) {
  _apiKey = key;
}

export function clearApiKey() {
  _apiKey = null;
}

export function getApiKey(): string | null {
  return _apiKey;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body?: unknown
  ) {
    super(`API Error ${status}: ${statusText}`);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${path}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };

  if (_apiKey) {
    headers["Authorization"] = `Bearer ${_apiKey}`;
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearApiKey();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiError(res.status, res.statusText);
  }

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    throw new ApiError(res.status, res.statusText, body);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}
