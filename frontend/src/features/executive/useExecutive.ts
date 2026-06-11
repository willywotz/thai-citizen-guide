import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchExecutiveSummary, regenerateExecutiveSummary } from '@/features/executive/executiveApi';

export function useExecutiveSummary() {
  return useQuery({
    queryKey: ['executive', 'summary'],
    queryFn: fetchExecutiveSummary,
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useRegenerateExecutiveSummary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: regenerateExecutiveSummary,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['executive', 'summary'] }),
  });
}
