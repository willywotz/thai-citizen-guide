import { useQuery } from '@tanstack/react-query';
import { fetchChatHistory } from '@/features/history/historyApi';
import { STALE_TIME } from '@/shared/constants/query';

export function useChatHistory(search?: string, filterAgency?: string) {
  return useQuery({
    queryKey: ['chatHistory', search, filterAgency],
    queryFn: () => fetchChatHistory(search, filterAgency),
    staleTime: STALE_TIME.normal,
  });
}
