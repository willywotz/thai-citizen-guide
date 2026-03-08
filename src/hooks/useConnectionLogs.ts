import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';

export interface ConnectionLog {
  id: string;
  agencyId: string;
  action: string;
  connectionType: string;
  status: string;
  latencyMs: number;
  detail: string;
  createdAt: string;
}

async function fetchConnectionLogs(agencyId: string): Promise<ConnectionLog[]> {
  try {
    return await api.get<ConnectionLog[]>(`/api/agencies/${agencyId}/connection-logs`);
  } catch (err) {
    console.warn('Failed to fetch connection logs', err);
    return [];
  }
}

export function useConnectionLogs(agencyId: string | undefined) {
  return useQuery({
    queryKey: ['connection-logs', agencyId],
    queryFn: () => fetchConnectionLogs(agencyId!),
    enabled: !!agencyId,
    staleTime: 15_000,
  });
}
