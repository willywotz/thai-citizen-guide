export interface Agency {
  id: string;
  name: string;
  shortName: string;
  logo: string;
  connectionType: 'MCP' | 'API' | 'A2A';
  status: 'active' | 'inactive';
  description: string;
  dataScope: string[];
  totalCalls: number;
  color: string;
}

export interface AgentStep {
  icon: string;
  label: string;
  detail?: string;
  status: 'pending' | 'active' | 'done';
}
