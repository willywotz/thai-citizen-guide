import { api } from '@/shared/lib/apiClient';
import { dashboardStats, agencyUsageData, weeklyTrendData, categoryData } from '@/shared/data/mockData';

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
