import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/lib/apiClient';
import type { ConversationMessage } from '@/shared/types/conversation';

async function fetchConversationMessages(conversationId: string): Promise<ConversationMessage[]> {
  const data = await api.get<ConversationMessage[]>(
    `/api/v1/conversations/${conversationId}/messages`
  );
  return data ?? [];
}

export function useConversationMessages(conversationId: string | null) {
  return useQuery({
    queryKey: ['conversationMessages', conversationId],
    queryFn: () => fetchConversationMessages(conversationId!),
    enabled: !!conversationId,
    staleTime: 60 * 1000,
  });
}
