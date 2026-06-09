import { useQuery } from '@tanstack/react-query';
import { fetchDashboardStats, fetchAgencyUsage, fetchWeeklyTrend, fetchCategoryData } from '@/services/dashboardApi';

const REFETCH_INTERVAL = 30 * 1000;

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: fetchDashboardStats,
    refetchInterval: REFETCH_INTERVAL,
  });
}

export function useAgencyUsage() {
  return useQuery({
    queryKey: ['dashboard', 'agencyUsage'],
    queryFn: fetchAgencyUsage,
    refetchInterval: REFETCH_INTERVAL,
  });
}

export function useWeeklyTrend() {
  return useQuery({
    queryKey: ['dashboard', 'weeklyTrend'],
    queryFn: fetchWeeklyTrend,
    refetchInterval: REFETCH_INTERVAL,
  });
}

export function useCategoryData() {
  return useQuery({
    queryKey: ['dashboard', 'categoryData'],
    queryFn: fetchCategoryData,
    refetchInterval: REFETCH_INTERVAL,
  });
}
