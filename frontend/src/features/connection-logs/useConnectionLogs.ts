import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/lib/apiClient';
import { ConnectionLog } from '@/shared/types/connectionLog';
import { REFETCH } from '@/shared/constants/query';

export interface ConnectionLogResponse {
  search: string | null;
  page: number;
  page_size: number;
  items: ConnectionLog[];
  total_items: number;

  total_connections: number;
  successful_connections: number;
  failed_connections: number;
  average_latency_ms: number;
}

export interface ConnectionLogParams {
  page?: number;
  limit?: number;
  search?: string;
  agencyId?: string;
}

async function fetchConnectionLogs(params: ConnectionLogParams = {}): Promise<ConnectionLogResponse> {
  const qs = new URLSearchParams();
  if (params.page) qs.set('page', String(params.page));
  if (params.limit) qs.set('limit', String(params.limit));
  if (params.search) qs.set('search', params.search);
  if (params.agencyId) qs.set('agency_id', params.agencyId);
  const query = qs.toString();
  return await api.get<ConnectionLogResponse>(`/api/v1/connection-logs${query ? `?${query}` : ''}`);
}

export function useConnectionLogs(params: ConnectionLogParams = {}) {
  return useQuery({
    queryKey: ['connection-logs', params.agencyId ?? null, params.page ?? null, params.limit ?? null, params.search ?? null],
    queryFn: () => fetchConnectionLogs(params),
    refetchInterval: REFETCH.normal,
    placeholderData: (prev) => prev,
    
    initialData: {
      search: null,
      page: 1,
      page_size: 20,
      items: [],
      total_items: 0,
      total_connections: 0,
      successful_connections: 0,
      failed_connections: 0,
      average_latency_ms: 0,
    },
  });
}

export interface ConnectionLogInfo {
  total_connections: number;
  successful_connections: number;
  failed_connections: number;
  average_latency_ms: number;
}

async function fetchConnectionLogInfo(): Promise<ConnectionLogInfo> {
  return await api.get<ConnectionLogInfo>('/api/v1/connection-logs/info');
}

export function useConnectionLogInfo() {
  return useQuery({
    queryKey: ['connection-log-info'],
    queryFn: fetchConnectionLogInfo,
    refetchInterval: REFETCH.normal,
  });
}