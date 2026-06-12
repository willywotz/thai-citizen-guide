import { api } from "@/shared/lib/apiClient";

export interface APIKey {
  id: string;
  name: string;
  key_prefix: string;
  last_used_at: string | null;
  created_at: string;
}

export interface CreatedAPIKey extends APIKey {
  key: string; // full key — shown only once on creation
}

export const listAPIKeys = (): Promise<APIKey[]> =>
  api.get<APIKey[]>("/api/v1/api-keys/");

export const createAPIKey = (name: string): Promise<CreatedAPIKey> =>
  api.post<CreatedAPIKey>("/api/v1/api-keys/", { name });

export const updateAPIKey = (id: string, name: string): Promise<APIKey> =>
  api.patch<APIKey>(`/api/v1/api-keys/${id}`, { name });

export const deleteAPIKey = (id: string): Promise<{ detail: string }> =>
  api.delete<{ detail: string }>(`/api/v1/api-keys/${id}`);
