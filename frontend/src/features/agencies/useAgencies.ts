import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/lib/apiClient';
// import { agencies as mockAgencies } from '@/shared/data/mockData';
import type { Agency } from '@/shared/types';
import type { AgencyRow } from '@/shared/types/agency';
import { mapRowToAgency } from '@/shared/types/agency';
import type { TestResult } from '@/features/agencies/ConnectionTestResult';

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

const emptyAgencies: Agency[] = [];

async function fetchAgencies(): Promise<Agency[]> {
  try {
    const res = await api.get<{ data: AgencyRow[]; total: number }>('/api/v1/agencies');
    if (!res.data || res.data.length === 0) return emptyAgencies;
    return res.data.map(mapRowToAgency);
  } catch (err) {
    console.warn('Failed to fetch agencies from backend, using fallback', err);
    return emptyAgencies;
  }
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useAgencies() {
  return useQuery({
    queryKey: ['agencies'],
    queryFn: fetchAgencies,
    staleTime: 30_000,
    refetchInterval: 60_000,   // poll every 60 s (replaces Supabase realtime)
  });
}

export function useCreateAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (agency: Partial<Agency>) => {
      return api.post('/api/v1/agencies', {
        name: agency.name,
        short_name: agency.shortName,
        logo: agency.logo,
        connection_type: agency.connectionType,
        status: agency.status,
        description: agency.description,
        data_scope: agency.dataScope ?? [],
        color: agency.color,
        endpoint_url: agency.endpointUrl,
        api_key_name: agency.apiKeyName,
        auth_method: agency.authMethod,
        auth_header: agency.authHeader,
        base_path: agency.basePath,
        rate_limit_rpm: agency.rateLimitRpm,
        request_format: agency.requestFormat,
        api_endpoints: agency.apiEndpoints ?? [],
        response_schema: agency.responseSchema ?? [],
        api_spec_raw: agency.apiSpecRaw,
        expected_payload: agency.expectedPayload ?? null,
        api_headers: agency.apiHeaders ?? [],
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agencies'] }),
  });
}

export function useUpdateAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (agency: Partial<Agency> & { id: string }) => {
      return api.patch(`/api/v1/agencies/${agency.id}`, {
        name: agency.name,
        short_name: agency.shortName,
        logo: agency.logo,
        connection_type: agency.connectionType,
        status: agency.status,
        description: agency.description,
        data_scope: agency.dataScope,
        color: agency.color,
        endpoint_url: agency.endpointUrl,
        api_key_name: agency.apiKeyName,
        auth_method: agency.authMethod,
        auth_header: agency.authHeader,
        base_path: agency.basePath,
        rate_limit_rpm: agency.rateLimitRpm,
        request_format: agency.requestFormat,
        api_endpoints: agency.apiEndpoints,
        response_schema: agency.responseSchema,
        api_spec_raw: agency.apiSpecRaw,
        expected_payload: agency.expectedPayload,
        api_headers: agency.apiHeaders,
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agencies'] }),
  });
}

export function useDeleteAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      return api.delete(`/api/v1/agencies/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agencies'] }),
  });
}

export function useTestConnection() {
  const qc = useQueryClient();

  return useMutation<TestResult, Error, { agencyId: string }>({
    mutationFn: async ({ agencyId }) => {
      return await api.get<TestResult>(`/api/v1/agencies/${agencyId}/test`);
    },
    onSuccess: (_data, variables) => {
      // Refresh the connection-logs list for this ag ency so the log panel
      // shows the new entry without a manual reload.
      qc.invalidateQueries({ queryKey: ['connection-logs', variables.agencyId] });
    },
  });
}
