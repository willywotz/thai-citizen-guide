import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';

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
  const { data, error } = await supabase
    .from('connection_logs' as any)
    .select('*')
    .eq('agency_id', agencyId)
    .order('created_at', { ascending: false })
    .limit(50);

  if (error) {
    console.warn('Failed to fetch connection logs', error.message);
    return [];
  }

  return ((data || []) as any[]).map((row: any) => ({
    id: row.id,
    agencyId: row.agency_id,
    action: row.action,
    connectionType: row.connection_type,
    status: row.status,
    latencyMs: row.latency_ms,
    detail: row.detail,
    createdAt: row.created_at,
  }));
}

export function useConnectionLogs(agencyId: string | undefined) {
  return useQuery({
    queryKey: ['connection-logs', agencyId],
    queryFn: () => fetchConnectionLogs(agencyId!),
    enabled: !!agencyId,
    staleTime: 15_000,
  });
}
