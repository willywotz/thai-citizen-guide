import { api } from '@/lib/apiClient';

export interface AgencyApiResponse {
  success: boolean;
  agency: string;
  agencyName: string;
  data: {
    answer: string;
    references: { title: string; url: string }[];
    confidence: number;
  };
  responseTime: number;
}

type AgencyId = 'fda' | 'revenue' | 'dopa' | 'land';

export async function queryAgency(agencyId: AgencyId, query: string): Promise<AgencyApiResponse> {
  return api.post<AgencyApiResponse>(`/api/chat/agency/${agencyId}`, { query });
}
