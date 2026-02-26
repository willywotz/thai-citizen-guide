import { useState, useEffect, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area,
} from "recharts";
import { MessageSquare, TrendingUp, Clock, ThumbsUp, Loader2, Activity } from "lucide-react";
import { useDashboardStats, useAgencyUsage, useWeeklyTrend, useCategoryData } from "@/hooks/useDashboard";
import { useAgencies } from "@/hooks/useAgencies";
import { cn } from "@/lib/utils";
import { useTheme } from "next-themes";
import { LiveActivityChart } from "@/components/dashboard/LiveActivityChart";
import { FeedbackAnalytics } from "@/components/dashboard/FeedbackAnalytics";

function AnimatedNumber({ value, suffix = "" }: { value: string; suffix?: string }) {
  return (
    <span className="tabular-nums">
      {value}{suffix}
    </span>
  );
}

const CHART_COLORS = [
  "hsl(145 55% 40%)",
  "hsl(213 70% 45%)",
  "hsl(25 85% 55%)",
  "hsl(280 50% 50%)",
];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-card px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-foreground">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} className="text-xs text-muted-foreground">
          {p.name}: <span className="font-semibold text-foreground">{p.value?.toLocaleString()}</span>
        </p>
      ))}
    </div>
  );
};

export default function DashboardPage() {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const { data: stats, isLoading: statsLoading, dataUpdatedAt } = useDashboardStats();
  const { data: agencyUsage, isLoading: usageLoading } = useAgencyUsage();
  const { data: weeklyTrend } = useWeeklyTrend();
  const { data: categoryStats } = useCategoryData();
  const { data: agencies } = useAgencies();

  // Theme-aware colors
  const chartColors = useMemo(() => ({
    grid: isDark ? "hsl(220 15% 25%)" : "hsl(214 25% 92%)",
    tick: isDark ? "hsl(215 15% 60%)" : "hsl(215 15% 50%)",
    primary: isDark ? "hsl(213 65% 60%)" : "hsl(213 70% 45%)",
    dotStroke: isDark ? "hsl(220 18% 14%)" : "white",
    palette: isDark
      ? ["hsl(145 50% 50%)", "hsl(213 65% 60%)", "hsl(25 80% 60%)", "hsl(280 45% 60%)"]
      : ["hsl(145 55% 40%)", "hsl(213 70% 45%)", "hsl(25 85% 55%)", "hsl(280 50% 50%)"],
  }), [isDark]);

  const [lastUpdated, setLastUpdated] = useState("");
  useEffect(() => {
    if (dataUpdatedAt) {
      setLastUpdated(new Date(dataUpdatedAt).toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    }
  }, [dataUpdatedAt]);

  const statCards = stats ? [
    { label: "คำถามทั้งหมด", value: stats.totalQuestions.toLocaleString(), icon: MessageSquare, trend: "+12%", trendUp: true, color: "text-primary" },
    { label: "คำถามวันนี้", value: stats.todayQuestions.toLocaleString(), icon: TrendingUp, trend: "+8%", trendUp: true, color: "text-success" },
    { label: "เวลาตอบเฉลี่ย", value: stats.avgResponseTime, icon: Clock, trend: "-0.3s", trendUp: true, color: "text-warning" },
    { label: "ความพึงพอใจ", value: `${stats.satisfactionRate}%`, icon: ThumbsUp, trend: "+2.1%", trendUp: true, color: "text-info" },
  ] : [];

  const totalUsage = agencyUsage?.reduce((sum, a) => sum + a.value, 0) || 1;

  if (statsLoading) {
    return (
      <div className="flex items-center justify-center h-[50vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between animate-fade-in">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Dashboard สถิติการใช้งาน</h2>
          <p className="text-xs text-muted-foreground mt-0.5">ภาพรวมการใช้งานระบบ AI ประสานงานภาครัฐ</p>
        </div>
        {lastUpdated && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted/50 px-3 py-1.5 rounded-full">
            <Activity className="h-3 w-3 text-success animate-pulse" />
            <span>Live</span>
            <span className="text-muted-foreground/60">•</span>
            <span>{lastUpdated}</span>
          </div>
        )}
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((s, i) => (
          <Card
            key={i}
            className={cn(
              "group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 animate-fade-in",
            )}
            style={{ animationDelay: `${i * 80}ms`, animationFillMode: "both" }}
          >
            <CardContent className="p-4 relative z-10">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-muted-foreground font-medium">{s.label}</span>
                <div className={cn("p-2 rounded-lg bg-muted/80 transition-colors group-hover:bg-primary/10", s.color)}>
                  <s.icon className="h-4 w-4" />
                </div>
              </div>
              <p className="text-2xl font-bold text-foreground tracking-tight">
                <AnimatedNumber value={s.value} />
              </p>
              <div className="flex items-center gap-1 mt-1.5">
                <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded-full", s.trendUp ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive")}>
                  {s.trend}
                </span>
                <span className="text-[10px] text-muted-foreground">vs สัปดาห์ก่อน</span>
              </div>
            </CardContent>
            {/* Decorative gradient */}
            <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.03] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          </Card>
        ))}
      </div>

      {/* Live Activity - Realtime */}
      <LiveActivityChart />

      {/* Charts Row 1 */}
      <div className="grid lg:grid-cols-2 gap-4">
        {/* Weekly Trend - Area Chart */}
        <Card className="animate-fade-in" style={{ animationDelay: "320ms", animationFillMode: "both" }}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">แนวโน้มการใช้งานรายสัปดาห์</CardTitle>
              <span className="text-[10px] text-muted-foreground bg-muted px-2 py-1 rounded-full">7 วันล่าสุด</span>
            </div>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={weeklyTrend} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradientQuestions" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={chartColors.primary} stopOpacity={isDark ? 0.25 : 0.3} />
                    <stop offset="95%" stopColor={chartColors.primary} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: chartColors.tick }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: chartColors.tick }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey="questions"
                  name="คำถาม"
                  stroke={chartColors.primary}
                  strokeWidth={2.5}
                  fill="url(#gradientQuestions)"
                  dot={{ r: 4, fill: chartColors.primary, stroke: chartColors.dotStroke, strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: chartColors.primary, stroke: chartColors.dotStroke, strokeWidth: 2 }}
                  animationDuration={1200}
                  animationEasing="ease-out"
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Agency Usage - Donut */}
        <Card className="animate-fade-in" style={{ animationDelay: "400ms", animationFillMode: "both" }}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">สัดส่วนการเรียกใช้หน่วยงาน</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="55%" height={220}>
                <PieChart>
                  <Pie
                    data={agencyUsage}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={85}
                    innerRadius={55}
                    paddingAngle={3}
                    cornerRadius={4}
                    animationDuration={1000}
                    animationEasing="ease-out"
                  >
                    {agencyUsage?.map((entry, i) => (
                      <Cell key={i} fill={chartColors.palette[i % chartColors.palette.length]} stroke="none" />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2.5">
                {agencyUsage?.map((entry, i) => (
                  <div key={i} className="group">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: chartColors.palette[i % chartColors.palette.length] }} />
                        <span className="text-foreground font-medium">{entry.name}</span>
                      </div>
                      <span className="text-muted-foreground">{((entry.value / totalUsage) * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden ml-[18px]">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${(entry.value / totalUsage) * 100}%`,
                          backgroundColor: chartColors.palette[i % chartColors.palette.length],
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid lg:grid-cols-2 gap-4">
        {/* Category Stats */}
        <Card className="animate-fade-in" style={{ animationDelay: "480ms", animationFillMode: "both" }}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">หมวดหมู่คำถามยอดนิยม</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={categoryStats} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: chartColors.tick }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="category" width={110} tick={{ fontSize: 11, fill: chartColors.tick }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar
                  dataKey="count"
                  name="จำนวน"
                  radius={[0, 6, 6, 0]}
                  animationDuration={1000}
                  animationEasing="ease-out"
                >
                  {categoryStats?.map((_, i) => (
                    <Cell key={i} fill={chartColors.palette[i % chartColors.palette.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Agency Connection Status */}
        <Card className="animate-fade-in" style={{ animationDelay: "560ms", animationFillMode: "both" }}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">สถานะการเชื่อมต่อหน่วยงาน</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2.5">
              {agencies?.map((a, i) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between p-3 bg-muted/40 rounded-lg border border-border/50 hover:bg-muted/70 hover:border-border transition-all duration-200 animate-fade-in"
                  style={{ animationDelay: `${600 + i * 60}ms`, animationFillMode: "both" }}
                >
                  <div className="flex items-center gap-3">
                    <div className="text-xl w-9 h-9 rounded-lg bg-card flex items-center justify-center shadow-sm border border-border/50">
                      {a.logo}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">{a.shortName}</p>
                      <p className="text-[10px] text-muted-foreground">{a.connectionType} Protocol</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground">{a.totalCalls?.toLocaleString()} calls</span>
                    <span className={cn(
                      "text-[10px] font-medium px-2.5 py-1 rounded-full flex items-center gap-1",
                      a.status === 'active'
                        ? 'bg-success/10 text-success'
                        : 'bg-destructive/10 text-destructive'
                    )}>
                      <span className={cn(
                        "w-1.5 h-1.5 rounded-full",
                        a.status === 'active' ? 'bg-success animate-pulse' : 'bg-destructive'
                      )} />
                      {a.status === 'active' ? 'Online' : 'Offline'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Feedback Analytics */}
      <FeedbackAnalytics />
    </div>
  );
}
