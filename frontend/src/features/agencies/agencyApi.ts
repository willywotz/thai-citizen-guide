import { api } from '@/shared/lib/apiClient';
import type { Agency, AgencyRow } from '@/shared/types/agency';
import { mapRowToAgency } from '@/shared/types/agency';

export interface ConformanceCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface ConformanceReport {
  ran_at: string;
  passed: boolean;
  checks: ConformanceCheck[];
}

/** Agencies owned by the current user. Same per-item shape as the main list. */
export async function getMyAgencies(): Promise<Agency[]> {
  const rows = await api.get<AgencyRow[]>('/api/v1/agencies/mine');
  return rows.map(mapRowToAgency);
}

/** Run the conformance battery for an agency (owner or admin). */
export async function runConformance(id: string): Promise<ConformanceReport> {
  return api.post<ConformanceReport>(`/api/v1/agencies/${id}/conformance`);
}

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

/**
 * Query a specific agency by routing to the unified /api/v1/chat endpoint
 * and requesting only that agency.
 *
 * NOTE: The FastAPI backend handles individual-agency queries the same way
 * as the combined chat — keyword detection picks the right handler.
 * If you need a dedicated per-agency endpoint in the future, add it to
 * app/routers/chat.py and update this function.
 */
export async function queryAgency(agencyId: AgencyId, query: string): Promise<AgencyApiResponse> {
  // Use the chat endpoint and extract the first (relevant) agency result
  const res = await api.post<{
    success: boolean;
    data: {
      answer: string;
      references: { agency: string; title: string; url: string }[];
      agentSteps: unknown[];
      agencies: { id: string; name: string; icon: string }[];
      confidence: number;
    };
    responseTime: number;
  }>('/api/v1/chat', { query });

  const agencyInfo = res.data.agencies.find((a) => a.id === agencyId) ?? res.data.agencies[0];

  return {
    success: res.success,
    agency: agencyId,
    agencyName: agencyInfo?.name ?? agencyId,
    data: {
      answer: res.data.answer,
      references: res.data.references.map(({ agency: _agency, ...ref }) => ref),
      confidence: res.data.confidence,
    },
    responseTime: res.responseTime,
  };
}
