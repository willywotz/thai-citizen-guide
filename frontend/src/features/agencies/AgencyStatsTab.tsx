import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";

interface HourlyBucket { time: string; count: number }
interface StatusSlice { name: string; value: number; color: string }

interface Props {
  hourlyData: HourlyBucket[];
  statusPieData: StatusSlice[];
}

export function AgencyStatsTab({ hourlyData, statusPieData }: Props) {
  return (
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
  );
}
