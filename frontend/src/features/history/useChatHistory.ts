import { useQuery } from '@tanstack/react-query';
import { fetchChatHistory } from '@/services/historyApi';

export function useChatHistory(search?: string, filterAgency?: string) {
  return useQuery({
    queryKey: ['chatHistory', search, filterAgency],
    queryFn: () => fetchChatHistory(search, filterAgency),
    staleTime: 30 * 1000,
  });
}
