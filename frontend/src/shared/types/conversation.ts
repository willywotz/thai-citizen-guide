export interface ConversationMessage {
  id: string;
  role: string;
  content: string;
  agent_steps: any;
  sources: any;
  rating: string | null;
  created_at: string;
}
