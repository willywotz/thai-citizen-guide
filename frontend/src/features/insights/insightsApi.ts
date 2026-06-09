import { api } from '@/shared/lib/apiClient';

export interface TopicCluster {
  topic: string;
  category: string;
  count: number;
  prevCount: number;
  change: number;
  sentiment: 'positive' | 'neutral' | 'negative';
}

export interface AnalyticsInsightsData {
  totalWeekQuestions: number;
  topicClusters: TopicCluster[];
  sentimentDist: { positive: number; neutral: number; negative: number };
  noAnswerByAgency: { agency: string; rate: number }[];
  dailyVolume: { day: string; questions: number }[];
  trendingTopics: TopicCluster[];
  decliningTopics: TopicCluster[];
  aiInsights: string;
  recommendations: string[];
  generatedAt: string;
}

export interface AgencyHealthData {
  agencies: {
    id: string;
    name: string;
    shortName: string;
    status: 'healthy' | 'degraded' | 'down';
    uptime: number;
    currentLatency: number;
    avgLatency: number;
    errorRate: number;
    requestsPerMin: number;
    lastCheckedAt: string;
  }[];
  historical: Array<Record<string, string | number>>;
  incidents: {
    agency: string;
    type: string;
    severity: 'info' | 'warning' | 'critical';
    message: string;
    occurredAt: string;
    resolvedAt: string;
  }[];
  slaCompliance: { agency: string; uptime: number; target: number; met: boolean }[];
  generatedAt: string;
}

export type HeatmapRange = '7d' | '30d' | '90d';

export interface UsageHeatmapData {
  range: HeatmapRange;
  days: number;
  sampleSize: number;
  totalMessages: number;
  days_labels: string[];
  hours: number[];
  agencies: { id: string; name: string }[];
  hourlyByAgency: { agency: string; agencyId: string; data: number[] }[];
  dayHourMatrix: { day: string; dayIndex: number; data: number[] }[];
  insights: {
    peakDay: string;
    peakHour: string;
    peakValue: number;
    totalRequests: number;
    businessHoursPercent: number;
    busiest: { agency: string; total: number; peakHour: number };
    recommendation: string;
  };
  generatedAt: string;
}

export async function fetchAnalyticsInsights(): Promise<AnalyticsInsightsData> {
  return api.get<AnalyticsInsightsData>('/api/v1/analytics-insights');
}

export async function fetchAgencyHealth(): Promise<AgencyHealthData> {
  return api.get<AgencyHealthData>('/api/v1/agency-health');
}

export async function fetchUsageHeatmap(range: HeatmapRange = '7d'): Promise<UsageHeatmapData> {
  return api.get<UsageHeatmapData>(`/api/v1/usage-heatmap?range=${range}`);
}