import { Card, CardContent } from "@/shared/components/ui/card";
import { Activity, CheckCircle2, Clock, XCircle } from "lucide-react";
import type { Agency } from "@/shared/types";

interface Stats {
  successRate: number;
  avgLatency: number;
  error: number;
}

interface Props {
  agency: Agency;
  stats: Stats;
}

export function AgencyDetailStats({ agency, stats }: Props) {
  return (
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
            <Clock className="h-3.5 w-3.5" /> ค่าเฉลี่ย Latency (24 ชม.)
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
  );
}
