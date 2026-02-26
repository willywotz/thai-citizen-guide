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
  endpointUrl: string;
  apiKeyName?: string | null;
  createdAt?: string;
  updatedAt?: string;
}

// DB row shape (snake_case) → mapped to Agency (camelCase)
export interface AgencyRow {
  id: string;
  name: string;
  short_name: string;
  logo: string;
  connection_type: string;
  status: string;
  description: string;
  data_scope: string[];
  total_calls: number;
  color: string;
  endpoint_url: string;
  api_key_name: string | null;
  created_at: string;
  updated_at: string;
}

export function mapRowToAgency(row: AgencyRow): Agency {
  return {
    id: row.id,
    name: row.name,
    shortName: row.short_name,
    logo: row.logo,
    connectionType: row.connection_type as Agency['connectionType'],
    status: row.status as Agency['status'],
    description: row.description,
    dataScope: row.data_scope,
    totalCalls: row.total_calls,
    color: row.color,
    endpointUrl: row.endpoint_url,
    apiKeyName: row.api_key_name,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

export interface AgentStep {
  icon: string;
  label: string;
  detail?: string;
  status: 'pending' | 'active' | 'done';
}
