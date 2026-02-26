import type { AgentStep } from './agency';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  agentSteps?: AgentStep[];
  sources?: { agency: string; url: string; title: string }[];
  rating?: 'up' | 'down' | null;
}

export interface ConversationHistory {
  id: string;
  title: string;
  preview: string;
  date: string;
  agencies: string[];
  status: 'success' | 'failed';
  messages: ChatMessage[];
}
