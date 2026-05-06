import { useExecutiveSummary } from '@/hooks/useExecutive';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { generateExecutiveReport } from '@/utils/exportExecutiveReport';
import {
  TrendingUp, TrendingDown, Users, Clock, DollarSign, Activity,
  FileDown, Sparkles, AlertCircle, ChevronUp, ChevronDown, Minus,
} from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  BarChart, Bar,
} from 'recharts';
import ReactMarkdown from 'react-markdown';
import { toast } from '@/hooks/use-toast';

function StatCard({
  icon: Icon, label, value, sublabel, trend, accent = 'primary',
}: {
  icon: any; label: string; value: string; sublabel?: string;
  trend?: number; accent?: 'primary' | 'success' | 'warning' | 'destructive';
}) {
  const accentMap = {
    primary: 'bg-primary/10 text-primary',
    success: 'bg-success/10 text-success',
    warning: 'bg-warning/10 text-warning',
    destructive: 'bg-destructive/10 text-destructive',
  };
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground font-medium">{label}</p>
            <p className="text-2xl font-bold">{value}</p>
            {sublabel && <p className="text-xs text-muted-foreground">{sublabel}</p>}
          </div>
          <div className={`p-2 rounded-lg ${accentMap[accent]}`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
        {trend !== undefined && (
          <div className="mt-3 flex items-center gap-1 text-xs">
            {trend >= 0 ? (
              <TrendingUp className="h-3 w-3 text-success" />
            ) : (
              <TrendingDown className="h-3 w-3 text-destructive" />
            )}
            <span className={trend >= 0 ? 'text-success font-semibold' : 'text-destructive font-semibold'}>
              {trend >= 0 ? '+' : ''}{trend}%
            </span>
            <span className="text-muted-foreground">เทียบกับเดือนก่อน</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function GradeBadge({ grade }: { grade: string }) {
  const colors: Record<string, string> = {
    A: 'bg-success/15 text-success border-success/30',
    B: 'bg-primary/15 text-primary border-primary/30',
    C: 'bg-warning/15 text-warning border-warning/30',
    D: 'bg-destructive/15 text-destructive border-destructive/30',
  };
  return (
    <Badge variant="outline" className={`${colors[grade] || ''} font-bold w-8 justify-center`}>
      {grade}
    </Badge>
  );
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'up') return <ChevronUp className="h-4 w-4 text-success" />;
  if (trend === 'down') return <ChevronDown className="h-4 w-4 text-destructive" />;
  return <Minus className="h-4 w-4 text-muted-foreground" />;
}

export default function ExecutivePage() {
  const { data, isLoading, error, refetch, isFetching } = useExecutiveSummary();

  const handleExport = () => {
    if (!data) return;
    try {
      generateExecutiveReport(data);
      toast({ title: 'สร้างรายงาน PDF สำเร็จ', description: 'ดาวน์โหลดเรียบร้อยแล้ว' });
    } catch (e) {
      toast({ title: 'เกิดข้อผิดพลาด', description: 'ไม่สามารถสร้างรายงานได้', variant: 'destructive' });
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-12 w-96" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32" />)}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6">
        <Card className="border-destructive/50">
          <CardContent className="p-8 text-center space-y-3">
            <AlertCircle className="h-10 w-10 mx-auto text-destructive" />
            <p className="font-semibold">ไม่สามารถโหลดข้อมูลผู้บริหารได้</p>
            <Button onClick={() => refetch()} variant="outline">ลองอีกครั้ง</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { kpis, agencyScorecard, monthlyTrend, topIssues, weeklyBrief, generatedAt } = data;

  return (
    <div className="p-6 space-y-6 mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight portal-gradient-text">
            Executive Dashboard
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            ภาพรวมเชิงกลยุทธ์สำหรับผู้บริหาร · อัปเดตล่าสุด {new Date(generatedAt).toLocaleString('th-TH')}
          </p>
        </div>
        {/* <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
            <Activity className="h-4 w-4 mr-2" />
            รีเฟรช
          </Button>
          <Button onClick={handleExport} className="gov-gradient text-white">
            <FileDown className="h-4 w-4 mr-2" />
            ส่งออกรายงาน PDF
          </Button>
        </div> */}
      </div>

      {/* Top KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Users}
          label="คำถามรวมเดือนนี้"
          value={kpis.thisMonthQuestions.toLocaleString()}
          sublabel={`${kpis.lastMonthQuestions.toLocaleString()} คำถามในเดือนก่อน`}
          trend={kpis.momGrowthQuestions}
          accent="primary"
        />
        <StatCard
          icon={Users}
          label="คำถามรวมปีนี้"
          value={kpis.thisYearQuestions.toLocaleString()}
          sublabel={`${kpis.lastYearQuestions.toLocaleString()} คำถามในปีก่อน`}
          trend={kpis.yoyGrowthQuestions}
          accent="primary"
        />
        <StatCard
          icon={Users}
          label="ประชาชนที่ได้รับบริการเดือนนี้"
          value={kpis.thisMonthCitizens.toLocaleString()}
          sublabel={`${kpis.lastMonthCitizens.toLocaleString()} คนในเดือนก่อน`}
          trend={kpis.momGrowthCitizens}
          accent="primary"
        />
        <StatCard
          icon={Users}
          label="ประชาชนที่ได้รับบริการปีนี้"
          value={kpis.thisYearCitizens.toLocaleString()}
          sublabel={`${kpis.lastYearCitizens.toLocaleString()} คนในปีก่อน`}
          trend={kpis.yoyGrowthCitizens}
          accent="primary"
        />
        {/* <StatCard
          icon={Clock}
          label="เวลาราชการที่ประหยัดได้"
          value={`${kpis.totalHoursSaved.toLocaleString()} ชม.`}
          sublabel="vs Call Center แบบเดิม"
          accent="success"
        />
        <StatCard
          icon={DollarSign}
          label="งบประมาณที่ประหยัดได้"
          value={`฿${(kpis.costSaved / 1000000).toFixed(2)}M`}
          sublabel={`${kpis.costSaved.toLocaleString()} บาท`}
          accent="warning"
        />
        <StatCard
          icon={Activity}
          label="คะแนนสุขภาพระบบ"
          value={`${kpis.healthScore}/100`}
          sublabel={kpis.healthScore >= 90 ? 'ดีเยี่ยม' : 'ดี'}
          accent={kpis.healthScore >= 90 ? 'success' : 'primary'}
        /> */}
      </div>

      {/* Health Breakdown + YoY */}
      {/* <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">สุขภาพระบบ (Health Score Breakdown)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1.5">
                <span className="font-medium">System Uptime</span>
                <span className="text-muted-foreground">{kpis.uptime}%</span>
              </div>
              <Progress value={kpis.uptime} className="h-2" />
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1.5">
                <span className="font-medium">ความพึงพอใจประชาชน</span>
                <span className="text-muted-foreground">{kpis.satisfaction}%</span>
              </div>
              <Progress value={kpis.satisfaction} className="h-2" />
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1.5">
                <span className="font-medium">เวลาตอบสนองเฉลี่ย</span>
                <span className="text-muted-foreground">{kpis.avgResponseTime} วินาที</span>
              </div>
              <Progress value={Math.max(0, 100 - (kpis.avgResponseTime - 1) * 20)} className="h-2" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">การเติบโต YoY</CardTitle>
            <CardDescription>เทียบกับช่วงเดียวกันปีก่อน</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-center py-4">
              <p className="text-5xl font-bold text-success">+{kpis.yoyGrowth}%</p>
              <p className="text-sm text-muted-foreground mt-2">การใช้งานเพิ่มขึ้น</p>
              <div className="mt-4 inline-flex items-center gap-2 text-xs bg-success/10 text-success px-3 py-1.5 rounded-full">
                <TrendingUp className="h-3 w-3" />
                <span className="font-semibold">เกินเป้าหมายปี</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div> */}

      {/* Trend Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">แนวโน้ม 12 เดือนย้อนหลัง</CardTitle>
          <CardDescription>จำนวนคำถามและความพึงพอใจ</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={monthlyTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" />
              <YAxis yAxisId="left" stroke="hsl(var(--muted-foreground))" />
              <YAxis yAxisId="right" orientation="right" stroke="hsl(var(--muted-foreground))" domain={[80, 100]} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
              />
              <Legend />
              <Line yAxisId="left" type="monotone" dataKey="questions" stroke="hsl(var(--primary))"
                strokeWidth={2} name="คำถาม" dot={{ r: 4 }} />
              <Line yAxisId="right" type="monotone" dataKey="satisfaction" stroke="hsl(var(--success))"
                strokeWidth={2} name="ความพึงพอใจ %" dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Two-column: Agency Scorecard + Top Issues */}
      {/* <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">บัตรคะแนนหน่วยงาน</CardTitle>
            <CardDescription>เปรียบเทียบประสิทธิภาพ</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {agencyScorecard.map((a) => (
              <div key={a.shortName} className="flex items-center justify-between p-3 rounded-lg bg-muted/40 hover:bg-muted/70 transition-colors">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{a.name}</p>
                  <div className="flex gap-3 text-xs text-muted-foreground mt-0.5">
                    <span>Uptime {a.uptime}%</span>
                    <span>{a.avgLatency}ms</span>
                    <span>😊 {a.satisfaction}%</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">{a.calls.toLocaleString()}</span>
                  <GradeBadge grade={a.grade} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">หัวข้อที่ประชาชนถามบ่อย</CardTitle>
            <CardDescription>5 อันดับสูงสุดในเดือนนี้</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={topIssues} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis type="number" stroke="hsl(var(--muted-foreground))" />
                <YAxis type="category" dataKey="topic" width={120} stroke="hsl(var(--muted-foreground))"
                  tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="count" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="space-y-1.5 mt-3 pt-3 border-t">
              {topIssues.map((t) => (
                <div key={t.topic} className="flex items-center justify-between text-xs">
                  <span className="truncate">{t.topic}</span>
                  <TrendIcon trend={t.trend} />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div> */}

      {/* AI Weekly Brief */}
      <Card className="border bg-white">
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10">
              <Sparkles className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">AI Weekly Executive Brief</CardTitle>
              <CardDescription>วิเคราะห์โดย AI สำหรับผู้บริหาร</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="prose prose-sm dark:prose-invert max-w-none text-foreground">
            {weeklyBrief ? (
              <ReactMarkdown>{weeklyBrief}</ReactMarkdown>
            ) : (
              <p className="text-muted-foreground">กำลังสร้างรายงานสรุป...</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}