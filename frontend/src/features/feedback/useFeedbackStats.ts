import { useQuery } from '@tanstack/react-query';
import { fetchFeedbackStats } from '@/features/chat/feedbackApi';

export function useFeedbackStats() {
  return useQuery({
    queryKey: ['feedbackStats'],
    queryFn: fetchFeedbackStats,
    staleTime: 30 * 1000,
  });
}
