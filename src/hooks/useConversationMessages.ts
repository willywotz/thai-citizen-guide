import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';

export interface ConversationMessage {
  id: string;
  role: string;
  content: string;
  agent_steps: any;
  sources: any;
  rating: string | null;
  created_at: string;
}

async function fetchConversationMessages(conversationId: string): Promise<ConversationMessage[]> {
  return api.get<ConversationMessage[]>(`/api/conversations/${conversationId}/messages`);
}

export function useConversationMessages(conversationId: string | null) {
  return useQuery({
    queryKey: ['conversationMessages', conversationId],
    queryFn: () => fetchConversationMessages(conversationId!),
    enabled: !!conversationId,
    staleTime: 60 * 1000,
  });
}
