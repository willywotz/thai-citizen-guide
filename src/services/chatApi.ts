import { api } from '@/lib/apiClient';
import type { AgentStep } from '@/types';

export interface ChatApiResponse {
  success: boolean;
  data: {
    answer: string;
    references: { agency: string; title: string; url: string }[];
    agentSteps: AgentStep[];
    agencies: { id: string; name: string; icon: string }[];
    confidence: number;
  };
  responseTime: number;
}

export async function sendChatQuery(query: string): Promise<ChatApiResponse> {
  return api.post<ChatApiResponse>('/api/chat', { query });
}
