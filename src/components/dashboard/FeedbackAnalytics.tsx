import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend,
} from "recharts";
import { ThumbsUp, ThumbsDown, TrendingUp, MessageSquareWarning } from "lucide-react";
import { useTheme } from "next-themes";
import { useFeedbackStats } from "@/hooks/useFeedbackStats";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-card px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-foreground">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} className="text-xs text-muted-foreground">
          {p.name}: <span className="font-semibold text-foreground">{p.value}</span>
        </p>
      ))}
    </div>
  );
};

export function FeedbackAnalytics() {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const { data: stats, isLoading } = useFeedbackStats();

  const colors = useMemo(() => ({
    grid: isDark ? "hsl(220 15% 25%)" : "hsl(214 25% 92%)",
    tick: isDark ? "hsl(215 15% 60%)" : "hsl(215 15% 50%)",
    up: isDark ? "hsl(145 50% 50%)" : "hsl(145 55% 40%)",
    down: isDark ? "hsl(0 60% 55%)" : "hsl(0 65% 50%)",
    rate: isDark ? "hsl(213 65% 60%)" : "hsl(213 70% 45%)",
  }), [isDark]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
        <Skeleton className="h-72" />
      </div>
    );
  }

  if (!stats || stats.totalRatings === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <MessageSquareWarning className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
          <p className="text-sm text-muted-foreground">ยังไม่มีข้อมูล Feedback</p>
          <p className="text-xs text-muted-foreground mt-1">ข้อมูลจะแสดงเมื่อผู้ใช้เริ่มให้คะแนนคำตอบ</p>
        </CardContent>
      </Card>
    );
  }

  const summaryCards = [
    { label: "Feedback ทั้งหมด", value: stats.totalRatings, icon: TrendingUp, color: "text-primary" },
    { label: "👍 พึงพอใจ", value: stats.upCount, icon: ThumbsUp, color: "text-success" },
    { label: "👎 ไม่พึงพอใจ", value: stats.downCount, icon: ThumbsDown, color: "text-destructive" },
    { label: "อัตราความพึงพอใจ", value: `${stats.satisfactionRate}%`, icon: TrendingUp, color: "text-info" },
  ];

  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold text-foreground">📊 Feedback Analytics</h3>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {summaryCards.map((s, i) => (
          <Card key={i}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted-foreground">{s.label}</span>
                <s.icon className={cn("h-4 w-4", s.color)} />
              </div>
              <p className="text-2xl font-bold text-foreground">{s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Daily Satisfaction Trend */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">แนวโน้มความพึงพอใจรายวัน (14 วัน)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={stats.dailyTrend} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: colors.tick }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: colors.tick }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="up" name="👍" stroke={colors.up} strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="down" name="👎" stroke={colors.down} strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Agency Breakdown */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">ความพึงพอใจแยกตามหน่วยงาน</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={stats.agencyBreakdown} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: colors.tick }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="agency" width={100} tick={{ fontSize: 10, fill: colors.tick }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="up" name="👍" stackId="a" fill={colors.up} radius={[0, 0, 0, 0]} />
                <Bar dataKey="down" name="👎" stackId="a" fill={colors.down} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Low-rated Questions */}
      {stats.lowRatedQuestions.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">คำถามที่ได้คะแนนต่ำ (ล่าสุด)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {stats.lowRatedQuestions.map((q, i) => (
                <div key={i} className="flex items-start gap-3 p-3 bg-destructive/5 border border-destructive/10 rounded-lg">
                  <ThumbsDown className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-foreground line-clamp-2">{q.content}</p>
                    {q.feedback_text && (
                      <p className="text-xs text-muted-foreground mt-1 italic">"{q.feedback_text}"</p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className="text-[10px] bg-muted px-2 py-0.5 rounded-full">{q.agency}</span>
                      <span className="text-[10px] text-muted-foreground">
                        {new Date(q.created_at).toLocaleDateString('th-TH')}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
