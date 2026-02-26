import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAgencies } from "@/hooks/useAgencies";

export default function AgenciesPage() {
  const { data: agencies } = useAgencies();

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">จัดการหน่วยงานที่เชื่อมต่อ</h2>
        <span className="text-xs text-muted-foreground">{agencies.length} หน่วยงาน</span>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {agencies.map((agency) => (
          <Card key={agency.id} className="overflow-hidden">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
                    style={{ backgroundColor: `${agency.color}15` }}>
                    {agency.logo}
                  </div>
                  <div>
                    <CardTitle className="text-sm">{agency.name}</CardTitle>
                    <p className="text-xs text-muted-foreground mt-0.5">{agency.description}</p>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className="text-[10px]">
                  {agency.connectionType}
                </Badge>
                <Badge className={`text-[10px] ${agency.status === 'active' ? 'bg-green-100 text-green-700 hover:bg-green-100' : 'bg-red-100 text-red-700 hover:bg-red-100'}`}>
                  {agency.status === 'active' ? 'Active' : 'Inactive'}
                </Badge>
              </div>

              <div>
                <p className="text-xs text-muted-foreground mb-1.5">ขอบเขตข้อมูล:</p>
                <div className="flex flex-wrap gap-1">
                  {agency.dataScope.map((scope, i) => (
                    <span key={i} className="text-[10px] bg-accent text-accent-foreground px-2 py-0.5 rounded-full">
                      {scope}
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-border">
                <span className="text-xs text-muted-foreground">จำนวนครั้งที่เรียกใช้</span>
                <span className="text-sm font-semibold text-foreground">{agency.totalCalls.toLocaleString()}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
