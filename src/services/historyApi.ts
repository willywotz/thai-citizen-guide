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
