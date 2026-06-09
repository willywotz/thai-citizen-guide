import { useAgencyHealth } from './useHealth';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Skeleton } from '@/shared/components/ui/skeleton';
import { Activity, AlertCircle, CheckCircle2, XCircle, Zap, Clock } from 'lucide-react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const STATUS_COLORS = {
  healthy: 'hsl(142 70% 45%)',
  degraded: 'hsl(35 90% 55%)',
  down: 'hsl(0 70% 55%)',
};

const STATUS_LABELS = {
  healthy: 'ปกติ',
  degraded: 'ช้า',
  down: 'ล่ม',
};

const AGENCY_COLORS = ['hsl(213 70% 50%)', 'hsl(280 60% 55%)', 'hsl(35 90% 55%)', 'hsl(160 60% 45%)'];

export default function HealthPage() {
  const { data, isLoading } = useAgencyHealth();

  if (isLoading || !data) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-12 w-96" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32" />)}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Activity className="h-7 w-7 text-primary" />
            Agency Health Monitoring
          </h1>
          <p className="text-muted-foreground mt-1">Real-time uptime, latency และ historical chart</p>
        </div>
        <Badge variant="outline" className="text-xs animate-pulse">
          ● Live (refresh ทุก 15 วินาที)
        </Badge>
      </div>

      {/* Real-time agency cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {data.agencies.map(a => (
          <Card key={a.id} className="relative overflow-hidden">
            <div
              className="absolute top-0 left-0 right-0 h-1"
              style={{ background: STATUS_COLORS[a.status] }}
            />
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{a.name}</CardTitle>
                {a.status === 'healthy' && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
                {a.status === 'degraded' && <AlertCircle className="h-4 w-4 text-amber-500" />}
                {a.status === 'down' && <XCircle className="h-4 w-4 text-red-500" />}
              </div>
              <CardDescription className="text-xs">{a.shortName}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground">Uptime</span>
                <span className="font-mono font-semibold">{a.uptime}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground flex items-center gap-1"><Zap className="h-3 w-3" /> Latency</span>
                <span className="font-mono font-semibold">{a.currentLatency}ms</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground">Error Rate</span>
                <span className="font-mono">{a.errorRate}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted-foreground">Req/min</span>
                <span className="font-mono">{a.requestsPerMin}</span>
              </div>
              <Badge
                className="w-full justify-center mt-2"
                style={{ background: STATUS_COLORS[a.status], color: 'white' }}
              >
                {STATUS_LABELS[a.status]}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Historical Latency Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Latency 24 ชั่วโมงย้อนหลัง</CardTitle>
          <CardDescription>หน่วย: มิลลิวินาที (ms)</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={data.historical}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} unit="ms" />
              <Tooltip contentStyle={{ background: 'hsl(var(--background))', border: '1px solid hsl(var(--border))', borderRadius: 8 }} />
              <Legend />
              {data.agencies.map((a, i) => (
                <Line
                  key={a.id}
                  type="monotone"
                  dataKey={`${a.id}_latency`}
                  name={a.shortName}
                  stroke={AGENCY_COLORS[i]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Two columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 hidden">
        {/* SLA */}
        {/* <Card>
          <CardHeader>
            <CardTitle className="text-base">SLA Compliance</CardTitle>
            <CardDescription>เป้าหมาย Uptime ≥ 99%</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.slaCompliance.map(s => (
                <div key={s.agency} className="space-y-1.5">
                  <div className="flex justify-between text-sm">
                    <span className="font-medium">{s.agency}</span>
                    <span className={`font-mono ${s.met ? 'text-emerald-600' : 'text-red-500'}`}>
                      {s.uptime}% / {s.target}%
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full ${s.met ? 'bg-emerald-500' : 'bg-red-500'}`}
                      style={{ width: `${Math.min(100, s.uptime)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card> */}

        {/* Incidents */}
        {/* <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Clock className="h-4 w-4" /> Incidents 24 ชม.ล่าสุด
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2.5">
              {data.incidents.map((inc, i) => (
                <div key={i} className="p-3 border rounded-lg space-y-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={inc.severity === 'critical' ? 'destructive' : inc.severity === 'warning' ? 'default' : 'secondary'}
                        className="text-[10px]"
                      >
                        {inc.severity.toUpperCase()}
                      </Badge>
                      <span className="text-sm font-medium">{inc.agency}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {new Date(inc.occurredAt).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">{inc.message}</p>
                </div>
              ))}
              {data.incidents.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-6">ไม่มี incidents</p>
              )}
            </div>
          </CardContent>
        </Card> */}
      </div>
    </div>
  );
}