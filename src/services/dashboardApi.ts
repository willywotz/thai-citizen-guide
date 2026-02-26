import { dashboardStats, agencyUsageData, weeklyTrendData, categoryData } from '@/data/mockData';
import type { DashboardStats } from '@/types';

// Currently returns mock data — will be replaced with API calls when backend is ready
export async function fetchDashboardStats(): Promise<DashboardStats> {
  return dashboardStats;
}

export async function fetchAgencyUsage() {
  return agencyUsageData;
}

export async function fetchWeeklyTrend() {
  return weeklyTrendData;
}

export async function fetchCategoryData() {
  return categoryData;
}
