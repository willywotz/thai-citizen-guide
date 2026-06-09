import { api } from '@/shared/lib/apiClient';
import { conversationHistory as fallback } from '@/shared/data/mockData';

export interface HistoryItem {
  id: string;
  title: string;
  preview: string;
  date: string;
  agencies: string[];
  status: 'success' | 'failed';
  messageCount?: number;
  responseTime?: string;
}

interface HistoryApiResponse {
  success: boolean;
  data: HistoryItem[];
  total: number;
  responseTime: number;
}

export async function fetchChatHistory(
  search?: string,
  filterAgency?: string
): Promise<HistoryItem[]> {
  try {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (filterAgency) params.set('filterAgency', filterAgency);

    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await api.get<HistoryApiResponse>(`/api/v1/conversations${query}`);

    if (res.success) return res.data;
    throw new Error('API unsuccessful');
  } catch {
    console.warn('History API failed, using fallback');
    return fallback as HistoryItem[];
  }
}

export interface SaveConversationInput {
  title: string;
  preview: string;
  agencies: string[];
  status: 'success' | 'failed';
  responseTime?: string;
  messages: {
    id?: string;
    role: 'user' | 'assistant';
    content: string;
    agentSteps?: unknown[];
    sources?: unknown[];
    rating?: string | null;
  }[];
}

export async function saveConversation(input: SaveConversationInput): Promise<string | null> {
  try {
    const res = await api.post<{ success: boolean; conversationId: string }>('/api/v1/conversations', {
      title: input.title,
      preview: input.preview,
      agencies: input.agencies,
      status: input.status,
      response_time: input.responseTime,
      messages: input.messages.map((m) => ({
        id: m.id ?? undefined,
        role: m.role,
        content: m.content,
        agent_steps: m.agentSteps ?? [],
        sources: m.sources ?? [],
        rating: m.rating ?? null,
      })),
    });
    return res.conversationId ?? null;
  } catch (err) {
    console.warn('Failed to save conversation:', err);
    return null;
  }
}

export async function deleteConversation(id: string): Promise<boolean> {
  try {
    await api.delete(`/api/v1/conversations/${id}`);
    return true;
  } catch (err) {
    console.warn('Failed to delete conversation:', err);
    return false;
  }
}
