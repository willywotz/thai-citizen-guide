import { useQuery } from '@tanstack/react-query';
import { fetchAnalyticsInsights } from '@/features/insights/insightsApi';

export function useAnalyticsInsights() {
  return useQuery({
    queryKey: ['analytics-insights'],
    queryFn: fetchAnalyticsInsights,
    staleTime: 5 * 60_000,
  });
}
