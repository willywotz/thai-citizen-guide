import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { agencies as mockAgencies } from '@/data/mockData';
import type { Agency } from '@/types';

async function fetchAgencies(): Promise<Agency[]> {
  try {
    const { data, error } = await supabase.functions.invoke('agencies-list');
    if (error) throw new Error(error.message);
    if (data?.success) return data.data as Agency[];
    throw new Error('API returned unsuccessful');
  } catch {
    console.warn('Agencies API failed, using fallback');
    return mockAgencies;
  }
}

export function useAgencies() {
  return useQuery({
    queryKey: ['agencies'],
    queryFn: fetchAgencies,
    staleTime: 5 * 60 * 1000,
    initialData: mockAgencies,
  });
}
