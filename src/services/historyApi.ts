import { supabase } from '@/integrations/supabase/client';
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
    const { data, error } = await supabase.functions.invoke('chat-history', {
      body: { search: search || '', filterAgency: filterAgency || '' },
    });
    if (error) throw error;
    const res = data as HistoryApiResponse;
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
    agentSteps?: any[];
    sources?: any[];
    rating?: string | null;
  }[];
}

export async function saveConversation(input: SaveConversationInput): Promise<string | null> {
  try {
    const { data, error } = await supabase.functions.invoke('save-conversation', {
      body: input,
    });
    if (error) throw error;
    return data?.conversationId || null;
  } catch (err) {
    console.warn('Failed to save conversation:', err);
    return null;
  }
}

export async function deleteConversation(id: string): Promise<boolean> {
  try {
    const { error } = await supabase
      .from('conversations' as any)
      .delete()
      .eq('id', id);
    if (error) throw error;
    return true;
  } catch (err) {
    console.warn('Failed to delete conversation:', err);
    return false;
  }
}