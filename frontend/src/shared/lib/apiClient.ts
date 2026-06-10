/**
 * Axios-based HTTP client for the FastAPI backend.
 *
 * Base URL:  VITE_API_BASE_URL  (default: http://localhost:8000)
 *
 * A request interceptor automatically attaches the JWT stored in
 * localStorage as  Authorization: Bearer <token>  on every request.
 *
 * A response interceptor unwraps Axios errors and surfaces the FastAPI
 * `detail` field as a plain Error message.
 *
 * Usage:
 *   import { api } from '@/shared/lib/apiClient';
 *   const data = await api.get<AgencyList>('/api/v1/agencies');
 *   const result = await api.post('/api/v1/chat', { query: '...' });
 */

import axios, { type AxiosInstance, type AxiosResponse } from 'axios';

// ---------------------------------------------------------------------------
// Token helpers  (used by useAuth)
// ---------------------------------------------------------------------------

const TOKEN_KEY = 'auth_token';

export const tokenStorage = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string): void => { localStorage.setItem(TOKEN_KEY, token); },
  clear: (): void => { localStorage.removeItem(TOKEN_KEY); },
};

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

var baseURL = import.meta.env.VITE_API_BASE_URL as string | undefined;

if (!baseURL || baseURL.trim() === '') {
  baseURL = window.location.origin;
}

const axiosInstance: AxiosInstance = axios.create({
  baseURL: baseURL,
  headers: { 'Content-Type': 'application/json' },
});

// -- Request interceptor: attach Bearer token --------------------------------
axiosInstance.interceptors.request.use((config) => {
  const token = tokenStorage.get();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// -- Response interceptor: surface FastAPI detail as Error ------------------
axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    const detail = error?.response?.data?.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join(', ')
          : error.message ?? 'Request failed';
    return Promise.reject(new Error(message));
  }
);

// ---------------------------------------------------------------------------
// Typed helper — returns response.data directly (matches the old api.* surface)
// ---------------------------------------------------------------------------

async function req<T>(fn: () => Promise<AxiosResponse<T>>): Promise<T> {
  const res = await fn();
  return res.data;
}

// ---------------------------------------------------------------------------
// Public API  (drop-in replacement for the old fetch-based api object)
// ---------------------------------------------------------------------------

export const api = {
  get: <T = unknown>(path: string, params?: Record<string, unknown>) =>
    req<T>(() => axiosInstance.get<T>(path, { params })),

  post: <T = unknown>(path: string, body?: unknown) =>
    req<T>(() => axiosInstance.post<T>(path, body)),

  put: <T = unknown>(path: string, body?: unknown) =>
    req<T>(() => axiosInstance.put<T>(path, body)),

  patch: <T = unknown>(path: string, body?: unknown) =>
    req<T>(() => axiosInstance.patch<T>(path, body)),

  delete: <T = unknown>(path: string) =>
    req<T>(() => axiosInstance.delete<T>(path)),
};

/** Raw axios instance — use when you need full AxiosResponse access. */
export { axiosInstance };
