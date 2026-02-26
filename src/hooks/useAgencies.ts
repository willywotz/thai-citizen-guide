import { useQuery } from '@tanstack/react-query';
import { agencies as mockAgencies } from '@/data/mockData';
import type { Agency } from '@/types';

async function fetchAgencies(): Promise<Agency[]> {
  // Currently returns mock data — will be replaced with API call when backend is ready
  return mockAgencies;
}

export function useAgencies() {
  return useQuery({
    queryKey: ['agencies'],
    queryFn: fetchAgencies,
    staleTime: 5 * 60 * 1000,
    initialData: mockAgencies,
  });
}
