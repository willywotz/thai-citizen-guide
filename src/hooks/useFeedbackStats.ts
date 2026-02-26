import { useQuery } from '@tanstack/react-query';
import { fetchFeedbackStats } from '@/services/feedbackApi';

export function useFeedbackStats() {
  return useQuery({
    queryKey: ['feedbackStats'],
    queryFn: fetchFeedbackStats,
    staleTime: 30 * 1000,
  });
}
