import { useQuery } from '@tanstack/react-query';
import { getUsage, type UsageParams } from './usageApi';

const KEY = 'usage-analytics';

export function useUsage(params: UsageParams) {
  return useQuery({
    queryKey: [KEY, params],
    queryFn: () => getUsage(params),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}
