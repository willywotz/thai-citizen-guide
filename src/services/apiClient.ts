/**
 * Shared HTTP client for the FastAPI backend.
 * Automatically attaches Supabase session JWT to all requests.
 */
import { supabase } from '@/integrations/supabase/client';

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

async function getAuthHeaders(): Promise<HeadersInit> {
  const { data: { session } } = await supabase.auth.getSession();
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }
  return headers;
}

export async function apiGet<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: await getAuthHeaders(),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail ?? `Request failed: ${resp.status}`);
  }
  return resp.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: await getAuthHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail ?? `Request failed: ${resp.status}`);
  }
  return resp.json();
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    headers: await getAuthHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail ?? `Request failed: ${resp.status}`);
  }
  return resp.json();
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: await getAuthHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail ?? `Request failed: ${resp.status}`);
  }
  return resp.json();
}

export async function apiDelete<T = { success: boolean }>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: await getAuthHeaders(),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail ?? `Request failed: ${resp.status}`);
  }
  return resp.json();
}
