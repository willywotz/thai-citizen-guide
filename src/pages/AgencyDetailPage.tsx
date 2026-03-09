import { useParams, useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, Activity, Clock, CheckCircle2, XCircle, Wifi, BarChart3, Loader2 } from "lucide-react";
import { useAgencies } from "@/hooks/useAgencies";
import { useConnectionLogs } from "@/hooks/useConnectionLogs";
import { ConnectionTestResult, type TestResult } from "@/components/agencies/ConnectionTestResult";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { useMemo, useState } from "react";
import { format } from "date-fns";
import { supabase } from "@/integrations/supabase/client";

const connectionTypeColors: Record<string, string> = {
  MCP: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  API: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  A2A: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

const statusColors: Record<string, string> = {
  success: "text-green-600 dark:text-green-400",
  error: "text-destructive",
};

export default function AgencyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: agencies = [], isLoading: agenciesLoading } = useAgencies();
  const { data: logs = [], isLoading: logsLoading } = useConnectionLogs(id);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testLoading, setTestLoading] = useState(false);

  const agency = agencies.find((a) => a.id === id);

  const handleTestConnection = async () => {
    if (!agency?.endpointUrl) return;
    setTestLoading(true);
    setTestResult(null);
    try {
      const { data, error } = await supabase.functions.invoke('agency-manage', {
        method: 'POST',
        body: { action: 'test', connection_type: agency.connectionType, endpoint_url: agency.endpointUrl },
      });
      if (error) throw error;
      setTestResult(data as TestResult);
    } catch {
      setTestResult({ success: false, protocol: 'REST API', version: '-', steps: [], latency: '0ms', error: 'Request failed' });
    } finally {
      setTestLoading(false);
    }
  };
  const stats = useMemo(() => {
    if (!logs.length) return { total: 0, success: 0, error: 0, avgLatency: 0, successRate: 0 };
    const success = logs.filter((l) => l.status === "success").length;
    const error = logs.filter((l) => l.status === "error").length;
    const avgLatency = Math.round(logs.reduce((s, l) => s + l.latencyMs, 0) / logs.length);
    return { total: logs.length, success, error, avgLatency, successRate: Math.round((success / logs.length) * 100) };
  }, [logs]);

  const hourlyData = useMemo(() => {
    const buckets: Record<string, number> = {};
    logs.forEach((l) => {
      const hour = format(new Date(l.createdAt), "MM/dd HH:00");
      buckets[hour] = (buckets[hour] || 0) + 1;
    });
    return Object.entries(buckets)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-12)
      .map(([time, count]) => ({ time, count }));
  }, [logs]);

  const statusPieData = useMemo(() => {
    return [
      { name: "สำเร็จ", value: stats.success, color: "hsl(152, 55%, 42%)" },
      { name: "ล้มเหลว", value: stats.error, color: "hsl(0, 72%, 55%)" },
    ].filter((d) => d.value > 0);
  }, [stats]);

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
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/agencies")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex items-center gap-3 flex-1">
          <div
            className="w-14 h-14 rounded-xl flex items-center justify-center text-3xl"
            style={{ backgroundColor: `${agency.color}15` }}
          >
            {agency.logo}
          </div>
          <div>
            <h1 className="text-xl font-semibold text-foreground">{agency.name}</h1>
            <p className="text-sm text-muted-foreground">{agency.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {agency.connectionType === "API" && agency.endpointUrl && (
            <Button variant="outline" size="sm" className="gap-1.5" onClick={handleTestConnection} disabled={testLoading}>
              {testLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wifi className="h-3.5 w-3.5" />}
              ทดสอบการเชื่อมต่อ
            </Button>
          )}
          <Badge className={connectionTypeColors[agency.connectionType] || ""}>
            {agency.connectionType}
          </Badge>
          <Badge
            className={
              agency.status === "active"
                ? "bg-green-100 text-green-700 hover:bg-green-100 dark:bg-green-900/30 dark:text-green-400"
                : "bg-red-100 text-red-700 hover:bg-red-100 dark:bg-red-900/30 dark:text-red-400"
            }
          >
            {agency.status === "active" ? "Active" : "Inactive"}
          </Badge>
        </div>
      </div>

      {/* Test Result */}
      {(testLoading || testResult) && (
        <ConnectionTestResult result={testResult} loading={testLoading} />
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <Activity className="h-3.5 w-3.5" /> การเรียกใช้ทั้งหมด
            </div>
            <p className="text-2xl font-bold text-foreground">{agency.totalCalls.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <CheckCircle2 className="h-3.5 w-3.5" /> อัตราสำเร็จ
            </div>
            <p className="text-2xl font-bold text-foreground">{stats.successRate}%</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <Clock className="h-3.5 w-3.5" /> ค่าเฉลี่ย Latency
            </div>
            <p className="text-2xl font-bold text-foreground">{stats.avgLatency} ms</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <XCircle className="h-3.5 w-3.5" /> ข้อผิดพลาด
            </div>
            <p className="text-2xl font-bold text-foreground">{stats.error}</p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="logs" className="space-y-4">
        <TabsList>
          <TabsTrigger value="logs">
            <Wifi className="h-4 w-4 mr-1.5" /> Connection Logs
          </TabsTrigger>
          <TabsTrigger value="stats">
            <BarChart3 className="h-4 w-4 mr-1.5" /> สถิติ
          </TabsTrigger>
          <TabsTrigger value="info">
            <Activity className="h-4 w-4 mr-1.5" /> ข้อมูลหน่วยงาน
          </TabsTrigger>
        </TabsList>

        {/* Logs Tab */}
        <TabsContent value="logs">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">ประวัติการเชื่อมต่อล่าสุด</CardTitle>
            </CardHeader>
            <CardContent>
              {logsLoading ? (
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : logs.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">ยังไม่มีประวัติการเชื่อมต่อ</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[140px]">เวลา</TableHead>
                      <TableHead className="w-[80px]">ประเภท</TableHead>
                      <TableHead className="w-[80px]">สถานะ</TableHead>
                      <TableHead className="w-[100px]">Latency</TableHead>
                      <TableHead>รายละเอียด</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {logs.map((log) => (
                      <TableRow key={log.id}>
                        <TableCell className="text-xs font-mono text-muted-foreground">
                          {format(new Date(log.createdAt), "dd/MM HH:mm:ss")}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-[10px]">
                            {log.action}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span className={`text-xs font-medium ${statusColors[log.status] || ""}`}>
                            {log.status === "success" ? "✓ สำเร็จ" : "✗ ล้มเหลว"}
                          </span>
                        </TableCell>
                        <TableCell className="text-xs font-mono">
                          {log.latencyMs} ms
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {log.detail}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Stats Tab */}
        <TabsContent value="stats">
          <div className="grid md:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">การเรียกใช้ตามช่วงเวลา</CardTitle>
              </CardHeader>
              <CardContent>
                {hourlyData.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-8">ไม่มีข้อมูล</p>
                ) : (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={hourlyData}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                      <XAxis dataKey="time" tick={{ fontSize: 10 }} className="fill-muted-foreground" />
                      <YAxis tick={{ fontSize: 10 }} className="fill-muted-foreground" />
                      <Tooltip />
                      <Bar dataKey="count" fill="hsl(213, 70%, 45%)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">สัดส่วนสถานะ</CardTitle>
              </CardHeader>
              <CardContent>
                {statusPieData.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-8">ไม่มีข้อมูล</p>
                ) : (
                  <div className="flex items-center justify-center">
                    <ResponsiveContainer width="100%" height={250}>
                      <PieChart>
                        <Pie
                          data={statusPieData}
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={90}
                          dataKey="value"
                          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                        >
                          {statusPieData.map((entry, index) => (
                            <Cell key={index} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Info Tab */}
        <TabsContent value="info">
          <Card>
            <CardContent className="pt-6 space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">ชื่อย่อ</p>
                  <p className="text-sm font-medium text-foreground">{agency.shortName}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">ประเภทการเชื่อมต่อ</p>
                  <p className="text-sm font-medium text-foreground">{agency.connectionType}</p>
                </div>
                <div className="md:col-span-2">
                  <p className="text-xs text-muted-foreground mb-1">Endpoint URL</p>
                  <p className="text-sm font-mono text-foreground break-all">{agency.endpointUrl || "-"}</p>
                </div>

                {/* API Configuration Details */}
                {agency.connectionType === "API" && (
                  <>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Auth Method</p>
                      <p className="text-sm font-medium text-foreground">{agency.authMethod || "api_key"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Auth Header</p>
                      <p className="text-sm font-mono text-foreground">{agency.authHeader || "-"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Base Path</p>
                      <p className="text-sm font-mono text-foreground">{agency.basePath || "-"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Rate Limit</p>
                      <p className="text-sm font-medium text-foreground">{agency.rateLimitRpm ? `${agency.rateLimitRpm} RPM` : "-"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Request Format</p>
                      <p className="text-sm font-medium text-foreground uppercase">{agency.requestFormat || "json"}</p>
                    </div>
                    {agency.apiEndpoints && agency.apiEndpoints.length > 0 && (
                      <div className="md:col-span-2">
                        <p className="text-xs text-muted-foreground mb-2">API Endpoints ({agency.apiEndpoints.length})</p>
                        <div className="border border-border rounded-md overflow-hidden">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead className="w-[80px] text-xs">Method</TableHead>
                                <TableHead className="text-xs">Path</TableHead>
                                <TableHead className="text-xs">คำอธิบาย</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {agency.apiEndpoints.map((ep, i) => (
                                <TableRow key={i}>
                                  <TableCell>
                                    <Badge variant="outline" className="text-[10px] font-mono">{ep.method}</Badge>
                                  </TableCell>
                                  <TableCell className="text-xs font-mono">{ep.path}</TableCell>
                                  <TableCell className="text-xs text-muted-foreground">{ep.description}</TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>
                      </div>
                    )}
                  </>
                )}

                <div className="md:col-span-2">
                  <p className="text-xs text-muted-foreground mb-1.5">ขอบเขตข้อมูล</p>
                  <div className="flex flex-wrap gap-1.5">
                    {agency.dataScope.map((scope, i) => (
                      <span
                        key={i}
                        className="text-[11px] bg-accent text-accent-foreground px-2.5 py-1 rounded-full"
                      >
                        {scope}
                      </span>
                    ))}
                  </div>
                </div>
                {agency.apiKeyName && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">API Key Name</p>
                    <p className="text-sm font-mono text-foreground">{agency.apiKeyName}</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
