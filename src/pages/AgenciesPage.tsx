import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Plus, Pencil, Trash2, Wifi, MoreVertical } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useAgencies, useCreateAgency, useUpdateAgency, useDeleteAgency, useTestConnection } from "@/hooks/useAgencies";
import { AgencyFormDialog } from "@/components/agencies/AgencyFormDialog";
import { DeleteAgencyDialog } from "@/components/agencies/DeleteAgencyDialog";
import { ConnectionTestResult } from "@/components/agencies/ConnectionTestResult";
import { toast } from "sonner";
import type { Agency } from "@/types";

const connectionTypeColors: Record<string, string> = {
  MCP: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  API: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  A2A: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

export default function AgenciesPage() {
  const navigate = useNavigate();
  const { data: agencies = [], isLoading } = useAgencies();
  const createMutation = useCreateAgency();
  const updateMutation = useUpdateAgency();
  const deleteMutation = useDeleteAgency();
  const testMutation = useTestConnection();

  const [formOpen, setFormOpen] = useState(false);
  const [editAgency, setEditAgency] = useState<Agency | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Agency | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, any>>({});

  const handleCreate = () => { setEditAgency(null); setFormOpen(true); };
  const handleEdit = (a: Agency) => { setEditAgency(a); setFormOpen(true); };

  const handleSave = async (data: Partial<Agency>) => {
    try {
      if (editAgency) {
        await updateMutation.mutateAsync({ ...data, id: editAgency.id } as Agency & { id: string });
        toast.success("อัปเดตหน่วยงานสำเร็จ");
      } else {
        await createMutation.mutateAsync(data);
        toast.success("เพิ่มหน่วยงานสำเร็จ");
      }
      setFormOpen(false);
    } catch (err: any) {
      toast.error(err.message || "เกิดข้อผิดพลาด");
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
      toast.success("ลบหน่วยงานสำเร็จ");
      setDeleteTarget(null);
    } catch (err: any) {
      toast.error(err.message || "เกิดข้อผิดพลาด");
    }
  };

  const handleTest = async (agency: Agency) => {
    setTestingId(agency.id);
    setTestResults((prev) => ({ ...prev, [agency.id]: null }));
    try {
      const result = await testMutation.mutateAsync({
        connectionType: agency.connectionType,
        endpointUrl: agency.endpointUrl || "",
      });
      setTestResults((prev) => ({ ...prev, [agency.id]: result }));
    } catch {
      setTestResults((prev) => ({ ...prev, [agency.id]: { success: false, error: "Connection failed" } }));
    } finally {
      setTestingId(null);
    }
  };

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">จัดการหน่วยงานที่เชื่อมต่อ</h2>
          <p className="text-xs text-muted-foreground mt-0.5">รองรับ MCP, A2A และ API สำหรับการสื่อสารระหว่าง AI Agent</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{agencies.length} หน่วยงาน</span>
          <Button size="sm" onClick={handleCreate}>
            <Plus className="h-4 w-4 mr-1" /> เพิ่มหน่วยงาน
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">กำลังโหลด...</div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {agencies.map((agency) => (
            <Card key={agency.id} className="overflow-hidden cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate(`/agencies/${agency.id}`)}>
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
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={(e) => e.stopPropagation()}>
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleEdit(agency)}>
                        <Pencil className="h-3.5 w-3.5 mr-2" /> แก้ไข
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleTest(agency)}>
                        <Wifi className="h-3.5 w-3.5 mr-2" /> ทดสอบการเชื่อมต่อ
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => setDeleteTarget(agency)} className="text-destructive">
                        <Trash2 className="h-3.5 w-3.5 mr-2" /> ลบ
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  <Badge className={`text-[10px] ${connectionTypeColors[agency.connectionType] || ''}`}>
                    {agency.connectionType}
                  </Badge>
                  <Badge className={`text-[10px] ${agency.status === 'active' ? 'bg-green-100 text-green-700 hover:bg-green-100 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-700 hover:bg-red-100 dark:bg-red-900/30 dark:text-red-400'}`}>
                    {agency.status === 'active' ? 'Active' : 'Inactive'}
                  </Badge>
                </div>

                {agency.endpointUrl && (
                  <p className="text-[10px] text-muted-foreground font-mono truncate">{agency.endpointUrl}</p>
                )}

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

                {/* Connection test result */}
                {(testingId === agency.id || testResults[agency.id]) && (
                  <ConnectionTestResult
                    result={testResults[agency.id]}
                    loading={testingId === agency.id}
                  />
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <AgencyFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        agency={editAgency}
        onSave={handleSave}
        saving={createMutation.isPending || updateMutation.isPending}
      />

      <DeleteAgencyDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        agencyName={deleteTarget?.name || ""}
        onConfirm={handleDelete}
        deleting={deleteMutation.isPending}
      />
    </div>
  );
}
