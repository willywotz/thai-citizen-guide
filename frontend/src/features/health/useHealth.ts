import { useQuery } from '@tanstack/react-query';
import { fetchAgencyHealth } from './healthApi';

export function useAgencyHealth() {
  return useQuery({
    queryKey: ['agency-health'],
    queryFn: fetchAgencyHealth,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });
}
