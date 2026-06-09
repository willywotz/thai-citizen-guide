import { useQuery } from '@tanstack/react-query';
import { fetchExecutiveSummary } from '@/services/executiveApi';

export function useExecutiveSummary() {
  return useQuery({
    queryKey: ['executive', 'summary'],
    queryFn: fetchExecutiveSummary,
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}