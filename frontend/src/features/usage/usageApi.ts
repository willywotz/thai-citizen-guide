import { api } from '@/shared/lib/apiClient';

export interface UsageRow {
  key: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  name?: string;
  key_prefix?: string;
  owner_email?: string | null;
}

export interface UsageParams {
  group_by: 'api_key';
  from?: string;
  to?: string;
}

export async function getUsage(params: UsageParams): Promise<UsageRow[]> {
  return api.get<UsageRow[]>('/api/v1/insight/usage', params);
}
