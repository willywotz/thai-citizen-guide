import { api } from '@/shared/lib/apiClient';
import { dashboardStats, agencyUsageData, weeklyTrendData, categoryData } from '@/shared/data/mockData';

export interface LlmUsageRow {
  key: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
}

interface DashboardApiResponse {
  success: boolean;
  data: {
    stats: typeof dashboardStats;
    agencyUsage: typeof agencyUsageData;
    weeklyTrend: typeof weeklyTrendData;
    categoryData: typeof categoryData;
  };
  responseTime: number;
}

async function fetchFromApi(): Promise<DashboardApiResponse> {
  return api.get<DashboardApiResponse>('/api/v1/dashboard/stats')
}

export async function fetchDashboardStats(): Promise<typeof dashboardStats> {
  try {
    const res = await fetchFromApi();
    return res.data.stats;
  } catch {
    return dashboardStats;
  }
}

export async function fetchAgencyUsage(): Promise<typeof agencyUsageData> {
  try {
    const res = await fetchFromApi();
    return res.data.agencyUsage;
  } catch {
    return [];
  }
}

export async function fetchWeeklyTrend(): Promise<typeof weeklyTrendData> {
  try {
    const res = await fetchFromApi();
    return res.data.weeklyTrend;
  } catch {
    return [];
  }
}

export async function fetchCategoryData(): Promise<typeof categoryData> {
  try {
    const res = await fetchFromApi();
    return res.data.categoryData;
  } catch {
    return [];
  }
}

export async function fetchLlmUsage(groupBy: string = "model"): Promise<LlmUsageRow[]> {
  try {
    return await api.get<LlmUsageRow[]>(`/api/v1/insight/usage?group_by=${groupBy}`);
  } catch {
    return [];
  }
}
