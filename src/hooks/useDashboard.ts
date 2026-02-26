import { useQuery } from '@tanstack/react-query';
import { fetchDashboardStats, fetchAgencyUsage, fetchWeeklyTrend, fetchCategoryData } from '@/services/dashboardApi';

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: fetchDashboardStats,
    staleTime: 30 * 1000,
  });
}

export function useAgencyUsage() {
  return useQuery({
    queryKey: ['dashboard', 'agencyUsage'],
    queryFn: fetchAgencyUsage,
    staleTime: 30 * 1000,
  });
}

export function useWeeklyTrend() {
  return useQuery({
    queryKey: ['dashboard', 'weeklyTrend'],
    queryFn: fetchWeeklyTrend,
    staleTime: 30 * 1000,
  });
}

export function useCategoryData() {
  return useQuery({
    queryKey: ['dashboard', 'categoryData'],
    queryFn: fetchCategoryData,
    staleTime: 30 * 1000,
  });
}
