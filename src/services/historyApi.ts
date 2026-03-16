import { apiGet, apiPost, apiDelete } from './apiClient';
import { conversationHistory as fallback } from '@/data/mockData';

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
    agentSteps?: any[];
    sources?: any[];
    rating?: string | null;
  }[];
}

export async function fetchChatHistory(
  search?: string,
  filterAgency?: string
): Promise<HistoryItem[]> {
  try {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (filterAgency) params.set('agency', filterAgency);
    const qs = params.toString() ? `?${params}` : '';
    return await apiGet<HistoryItem[]>(`/conversations${qs}`);
  } catch {
    console.warn('History API failed, using fallback');
    return fallback as HistoryItem[];
  }
}

export async function saveConversation(input: SaveConversationInput): Promise<string | null> {
  try {
    const res = await apiPost<{ success: boolean; conversationId: string }>('/conversations', input);
    return res.conversationId ?? null;
  } catch (err) {
    console.warn('Failed to save conversation:', err);
    return null;
  }
}

export async function deleteConversation(id: string): Promise<boolean> {
  try {
    await apiDelete(`/conversations/${id}`);
    return true;
  } catch (err) {
    console.warn('Failed to delete conversation:', err);
    return false;
  }
}
