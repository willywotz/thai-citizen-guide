import { api } from "@/shared/lib/apiClient";

export type APIKeyStatus = "active" | "expired" | "revoked";

export interface APIKey {
  id: string;
  name: string;
  key_prefix: string;
  last_used_at: string | null;
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  rate_limit_rpm: number | null;
  status: APIKeyStatus;
}

export interface CreatedAPIKey extends APIKey {
  key: string; // full key — shown only once on creation
}

export interface CreateAPIKeyRequest {
  name: string;
  expires_in_days?: number | null;
  rate_limit_rpm?: number | null;
}

export const listAPIKeys = (): Promise<APIKey[]> =>
  api.get<APIKey[]>("/api/v1/api-keys/");

export const createAPIKey = (body: CreateAPIKeyRequest): Promise<CreatedAPIKey> =>
  api.post<CreatedAPIKey>("/api/v1/api-keys/", body);

export const updateAPIKey = (id: string, name: string): Promise<APIKey> =>
  api.patch<APIKey>(`/api/v1/api-keys/${id}`, { name });

export const revokeAPIKey = (id: string): Promise<APIKey> =>
  api.post<APIKey>(`/api/v1/api-keys/${id}/revoke`, {});

export const deleteAPIKey = (id: string): Promise<{ detail: string }> =>
  api.delete<{ detail: string }>(`/api/v1/api-keys/${id}`);
