import { supabase } from '@/integrations/supabase/client';
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
  const { data, error } = await supabase.functions.invoke('ai-chat', {
    body: { query },
  });

  if (error) throw new Error(error.message);
  return data as ChatApiResponse;
}
