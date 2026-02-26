import { supabase } from '@/integrations/supabase/client';

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

const functionNameMap: Record<AgencyId, string> = {
  fda: 'agency-fda',
  revenue: 'agency-revenue',
  dopa: 'agency-dopa',
  land: 'agency-land',
};

export async function queryAgency(agencyId: AgencyId, query: string): Promise<AgencyApiResponse> {
  const fnName = functionNameMap[agencyId];
  const { data, error } = await supabase.functions.invoke(fnName, {
    body: { query },
  });

  if (error) throw new Error(error.message);
  return data as AgencyApiResponse;
}
