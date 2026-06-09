import { useQuery } from '@tanstack/react-query';
import { fetchAnalyticsInsights } from '@/services/insightsApi';

export function useAnalyticsInsights() {
  return useQuery({
    queryKey: ['analytics-insights'],
    queryFn: fetchAnalyticsInsights,
    staleTime: 5 * 60_000,
  });
}
