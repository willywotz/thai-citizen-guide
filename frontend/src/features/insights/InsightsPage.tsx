import { useAnalyticsInsights } from './useInsights';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Skeleton } from '@/shared/components/ui/skeleton';
import { Sparkles, TrendingUp, TrendingDown, Minus, MessageSquare, AlertTriangle, Lightbulb } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export default function InsightsPage() {
  const { data, isLoading } = useAnalyticsInsights();

  if (isLoading || !data) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-12 w-96" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-32" />)}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  const sentimentData = [
    { name: 'บวก', value: data.sentimentDist.positive, color: 'hsl(142 70% 45%)' },
    { name: 'กลาง', value: data.sentimentDist.neutral, color: 'hsl(213 70% 55%)' },
    { name: 'ลบ', value: data.sentimentDist.negative, color: 'hsl(0 70% 55%)' },
  ];

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Sparkles className="h-7 w-7 text-primary" />
            Analytics Insights AI
          </h1>
          <p className="text-muted-foreground mt-1">วิเคราะห์ trend คำถามรายสัปดาห์ด้วย AI</p>
        </div>
        <Badge variant="outline" className="text-xs">
          อัปเดตล่าสุด: {new Date(data.generatedAt).toLocaleString('th-TH')}
        </Badge>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>คำถามรวมสัปดาห์นี้</CardDescription>
            <CardTitle className="text-3xl">{data.totalWeekQuestions.toLocaleString()}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <MessageSquare className="h-3 w-3" /> ข้อความจากประชาชน
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>หัวข้อมาแรง</CardDescription>
            <CardTitle className="text-3xl text-emerald-600">{data.trendingTopics.length}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <TrendingUp className="h-3 w-3" /> เพิ่มขึ้น &gt;30% WoW
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Sentiment เชิงบวก</CardDescription>
            <CardTitle className="text-3xl text-primary">{data.sentimentDist.positive}%</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">ความพึงพอใจของผู้ใช้</p>
          </CardContent>
        </Card>
      </div>

      {/* AI Summary */}
      <Card className="border-primary/30 bg-primary/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Sparkles className="h-5 w-5 text-primary" />
            AI Weekly Insights
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm leading-relaxed whitespace-pre-line text-foreground/90">
            {data.aiInsights || 'กำลังประมวลผล...'}
          </p>
          {data.recommendations.length > 0 && (
            <div>
              <h4 className="font-semibold text-sm mb-2 flex items-center gap-1">
                <Lightbulb className="h-4 w-4 text-amber-500" /> ข้อเสนอแนะ
              </h4>
              <ul className="space-y-1.5">
                {data.recommendations.map((r, i) => (
                  <li key={i} className="text-sm flex gap-2">
                    <span className="text-primary font-medium">{i + 1}.</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">ปริมาณคำถามรายวัน</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={data.dailyVolume}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="day" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <Tooltip contentStyle={{ background: 'hsl(var(--background))', border: '1px solid hsl(var(--border))', borderRadius: 8 }} />
                <Bar dataKey="questions" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Sentiment Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={sentimentData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={3}>
                  {sentimentData.map((e, i) => <Cell key={i} fill={e.color} />)}
                </Pie>
                <Tooltip contentStyle={{ background: 'hsl(var(--background))', border: '1px solid hsl(var(--border))', borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex justify-around mt-2 text-xs">
              {sentimentData.map(s => (
                <div key={s.name} className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: s.color }} />
                  {s.name} {s.value}%
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Topic clusters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">หัวข้อยอดนิยม (Topic Clusters)</CardTitle>
          <CardDescription>เปรียบเทียบกับสัปดาห์ก่อน</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {data.topicClusters.map((t, i) => (
              <div key={i} className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent/50 transition">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="text-sm font-medium text-muted-foreground w-6">{i + 1}</div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{t.topic}</p>
                    <p className="text-xs text-muted-foreground">{t.category}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm font-mono">{t.count.toLocaleString()}</span>
                  <Badge
                    variant={t.change > 30 ? 'default' : t.change < -10 ? 'destructive' : 'secondary'}
                    className="min-w-[70px] justify-center"
                  >
                    {t.change > 0 ? <TrendingUp className="h-3 w-3 mr-1" /> : t.change < 0 ? <TrendingDown className="h-3 w-3 mr-1" /> : <Minus className="h-3 w-3 mr-1" />}
                    {t.change > 0 ? '+' : ''}{t.change}%
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* No-answer rate */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            No-Answer Rate ตามหน่วยงาน
          </CardTitle>
          <CardDescription>หน่วยงานที่ AI ตอบไม่ได้บ่อย ควรเสริม knowledge base</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.noAnswerByAgency} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis type="number" stroke="hsl(var(--muted-foreground))" fontSize={12} unit="%" />
              <YAxis dataKey="agency" type="category" stroke="hsl(var(--muted-foreground))" fontSize={12} width={100} />
              <Tooltip contentStyle={{ background: 'hsl(var(--background))', border: '1px solid hsl(var(--border))', borderRadius: 8 }} formatter={(v: number) => `${v}%`} />
              <Bar dataKey="rate" fill="hsl(35 90% 55%)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}