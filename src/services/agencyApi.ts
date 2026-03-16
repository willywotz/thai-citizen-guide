import { apiPost, apiGet } from './apiClient';
import type { Agency } from '@/types';

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
  const res = await apiPost<{
    success: boolean;
    data: { answer: string; references: { agency: string; title: string; url: string }[]; agencies: { id: string; name: string; icon: string }[]; confidence: number };
    responseTime: number;
  }>('/chat', { query, agency_filter: agencyId });

  const agencyMeta = res.data.agencies?.find(a => a.id === agencyId);
  return {
    success: res.success,
    agency: agencyId,
    agencyName: agencyMeta?.name ?? agencyId,
    data: {
      answer: res.data.answer,
      references: res.data.references
        .filter(r => r.agency === agencyId)
        .map(r => ({ title: r.title, url: r.url })),
      confidence: res.data.confidence,
    },
    responseTime: res.responseTime,
  };
}

export async function fetchAgencies(): Promise<Agency[]> {
  return apiGet<Agency[]>('/agencies');
}
