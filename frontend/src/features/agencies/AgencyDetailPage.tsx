import { useParams, useNavigate } from "react-router-dom";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { Button } from "@/shared/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { ArrowLeft, Wifi, BarChart3, Activity } from "lucide-react";
import { useMemo } from "react";
import { format } from "date-fns";
import { useAgencies, useTestConnection } from "./useAgencies";
import { useConnectionLogs } from "@/features/connection-logs/useConnectionLogs";
import { ConnectionTestResult } from "./ConnectionTestResult";
import { AgencyDetailHeader } from "./AgencyDetailHeader";
import { AgencyDetailStats } from "./AgencyDetailStats";
import { AgencyConnectionLogsTab } from "./AgencyConnectionLogsTab";
import { AgencyStatsTab } from "./AgencyStatsTab";
import { AgencyInfoTab } from "./AgencyInfoTab";

export default function AgencyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: agencies = [], isLoading: agenciesLoading } = useAgencies();
  const { data: logs, isLoading: logsLoading } = useConnectionLogs({ agencyId: id });
  const testMutation = useTestConnection();

  const agency = agencies.find((a) => a.id === id);

  const stats = useMemo(() => {
    if (!logs) return { total: 0, success: 0, error: 0, avgLatency: 0, successRate: 0 };
    const success = logs.successful_connections;
    const error = logs.failed_connections;
    return {
      total: logs.total_connections,
      success,
      error,
      avgLatency: logs.average_latency_ms,
      successRate: logs.total_connections > 0 ? Math.round((success / logs.total_connections) * 100) : 0,
    };
  }, [logs]);

  const hourlyData = useMemo(() => {
    const buckets: Record<string, number> = {};
    logs.items.forEach((l) => {
      const hour = format(new Date(l.created_at), "MM/dd HH:00");
      buckets[hour] = (buckets[hour] || 0) + 1;
    });
    return Object.entries(buckets)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-12)
      .map(([time, count]) => ({ time, count }));
  }, [logs]);

  const statusPieData = useMemo(() => [
    { name: "สำเร็จ", value: stats.success, color: "hsl(152, 55%, 42%)" },
    { name: "ล้มเหลว", value: stats.error, color: "hsl(0, 72%, 55%)" },
  ].filter((d) => d.value > 0), [stats]);

  if (agenciesLoading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!agency) {
    return (
      <div className="p-4 md:p-6 text-center space-y-4">
        <p className="text-muted-foreground">ไม่พบหน่วยงาน</p>
        <Button variant="outline" onClick={() => navigate("/agencies")}>
          <ArrowLeft className="h-4 w-4 mr-2" /> กลับ
        </Button>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <AgencyDetailHeader
        agency={agency}
        testMutation={testMutation}
        onBack={() => navigate("/agencies")}
        onTestConnection={() => testMutation.mutateAsync({ agencyId: agency.id })}
      />

      {(testMutation.isPending || testMutation.data || testMutation.isError) && (
        <ConnectionTestResult
          result={testMutation.data ?? (testMutation.isError
            ? { success: false, protocol: agency.connectionType, version: '-', steps: [], latency: '0ms', error: testMutation.error?.message ?? 'Request failed' }
            : null)}
          loading={testMutation.isPending}
        />
      )}

      <AgencyDetailStats agency={agency} stats={stats} />

      <Tabs defaultValue="logs" className="space-y-4">
        <TabsList>
          <TabsTrigger value="logs"><Wifi className="h-4 w-4 mr-1.5" /> Connection Logs</TabsTrigger>
          <TabsTrigger value="stats"><BarChart3 className="h-4 w-4 mr-1.5" /> สถิติ</TabsTrigger>
          <TabsTrigger value="info"><Activity className="h-4 w-4 mr-1.5" /> ข้อมูลหน่วยงาน</TabsTrigger>
        </TabsList>
        <TabsContent value="logs">
          <AgencyConnectionLogsTab logs={logs} logsLoading={logsLoading} />
        </TabsContent>
        <TabsContent value="stats">
          <AgencyStatsTab hourlyData={hourlyData} statusPieData={statusPieData} />
        </TabsContent>
        <TabsContent value="info">
          <AgencyInfoTab agency={agency} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
