import { apiGet } from './apiClient';
import type { DashboardStats } from '@/types';
import { dashboardStats as fallbackStats, agencyUsageData, weeklyTrendData, categoryData } from '@/data/mockData';

interface DashboardApiResponse {
  success: boolean;
  data: {
    stats: DashboardStats;
    agencyUsage: typeof agencyUsageData;
    weeklyTrend: typeof weeklyTrendData;
    categoryData: typeof categoryData;
  };
}

async function fetchFromApi(): Promise<DashboardApiResponse> {
  return apiGet<DashboardApiResponse>('/dashboard/stats');
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  try {
    const res = await fetchFromApi();
    return res.data.stats;
  } catch {
    console.warn('Dashboard API failed, using fallback');
    return fallbackStats;
  }
}

export async function fetchAgencyUsage() {
  try {
    const res = await fetchFromApi();
    return res.data.agencyUsage;
  } catch {
    return agencyUsageData;
  }
}

export async function fetchWeeklyTrend() {
  try {
    const res = await fetchFromApi();
    return res.data.weeklyTrend;
  } catch {
    return weeklyTrendData;
  }
}

export async function fetchCategoryData() {
  try {
    const res = await fetchFromApi();
    return res.data.categoryData;
  } catch {
    return categoryData;
  }
}
