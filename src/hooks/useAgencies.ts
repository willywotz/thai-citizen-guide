import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';
import { agencies as mockAgencies } from '@/data/mockData';
import type { Agency } from '@/types';

async function fetchAgencies(): Promise<Agency[]> {
  try {
    const data = await api.get<any[]>('/api/agencies');
    if (!data || data.length === 0) return mockAgencies;
    return data.map((a) => ({
      id: a.id,
      name: a.name,
      shortName: a.shortName,
      logo: a.logo,
      connectionType: a.connectionType,
      status: a.status,
      description: a.description,
      dataScope: a.dataScope || [],
      totalCalls: a.totalCalls || 0,
      color: a.color,
      endpointUrl: a.endpointUrl,
      apiKeyName: a.apiKeyName,
    }));
  } catch (err) {
    console.warn('Failed to fetch agencies from API, using fallback', err);
    return mockAgencies;
  }
}

export function useAgencies() {
  return useQuery({
    queryKey: ['agencies'],
    queryFn: fetchAgencies,
    staleTime: 30_000,
    refetchInterval: 30_000, // Poll every 30s instead of realtime
  });
}

export function useCreateAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (agency: Partial<Agency>) => {
      const data = await api.post('/api/agencies', {
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
      });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agencies'] }),
  });
}

export function useUpdateAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (agency: Partial<Agency> & { id: string }) => {
      const data = await api.put(`/api/agencies/${agency.id}`, {
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
      });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agencies'] }),
  });
}

export function useDeleteAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/agencies/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agencies'] }),
  });
}

export function useTestConnection() {
  return useMutation({
    mutationFn: async (params: { connectionType: string; endpointUrl: string }) => {
      return api.post('/api/agencies/test-connection', {
        connection_type: params.connectionType,
        endpoint_url: params.endpointUrl,
      });
    },
  });
}
