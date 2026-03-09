import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { agencies as mockAgencies } from '@/data/mockData';
import type { Agency } from '@/types';
import type { AgencyRow } from '@/types/agency';
import { mapRowToAgency } from '@/types/agency';
import { useEffect } from 'react';

async function fetchAgencies(): Promise<Agency[]> {
  const { data, error } = await supabase
    .from('agencies' as any)
    .select('*')
    .order('created_at', { ascending: true });

  if (error) {
    console.warn('Failed to fetch agencies from DB, using fallback', error.message);
    return mockAgencies;
  }

  if (!data || data.length === 0) return mockAgencies;
  return (data as unknown as AgencyRow[]).map(mapRowToAgency);
}

export function useAgencies() {
  const queryClient = useQueryClient();

  // Realtime subscription
  useEffect(() => {
    const channel = supabase
      .channel('agencies-realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'agencies' }, () => {
        queryClient.invalidateQueries({ queryKey: ['agencies'] });
      })
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [queryClient]);

  return useQuery({
    queryKey: ['agencies'],
    queryFn: fetchAgencies,
    staleTime: 30_000,
  });
}

export function useCreateAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (agency: Partial<Agency>) => {
      const { data, error } = await supabase.functions.invoke('agency-manage', {
        method: 'POST',
        body: {
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
          api_spec_raw: agency.apiSpecRaw,
        },
      });
      if (error) throw new Error(error.message);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agencies'] }),
  });
}

export function useUpdateAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (agency: Partial<Agency> & { id: string }) => {
      const { data, error } = await supabase.functions.invoke('agency-manage', {
        method: 'PUT',
        body: {
          id: agency.id,
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
          api_spec_raw: agency.apiSpecRaw,
        },
      });
      if (error) throw new Error(error.message);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agencies'] }),
  });
}

export function useDeleteAgency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data, error } = await supabase.functions.invoke('agency-manage', {
        method: 'DELETE',
        body: { id },
      });
      if (error) throw new Error(error.message);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agencies'] }),
  });
}

export function useTestConnection() {
  return useMutation({
    mutationFn: async (params: { connectionType: string; endpointUrl: string }) => {
      const { data, error } = await supabase.functions.invoke('agency-manage', {
        method: 'POST',
        body: {
          action: 'test',
          connection_type: params.connectionType,
          endpoint_url: params.endpointUrl,
        },
      });
      if (error) throw new Error(error.message);
      return data;
    },
  });
}
