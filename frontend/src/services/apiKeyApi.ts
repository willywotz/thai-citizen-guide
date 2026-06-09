import { api } from "@/shared/lib/apiClient";

export interface APIKey {
  id: string;
  name: string;
  key: string;
  created_at: string;
}

export const listAPIKeys = (): Promise<APIKey[]> =>
  api.get<APIKey[]>("/api/v1/api-keys/");

export const createAPIKey = (name: string): Promise<APIKey> =>
  api.post<APIKey>("/api/v1/api-keys/", { name });

export const updateAPIKey = (id: string, name: string): Promise<APIKey> =>
  api.patch<APIKey>(`/api/v1/api-keys/${id}`, { name });

export const deleteAPIKey = (id: string): Promise<{ detail: string }> =>
  api.delete<{ detail: string }>(`/api/v1/api-keys/${id}`);
