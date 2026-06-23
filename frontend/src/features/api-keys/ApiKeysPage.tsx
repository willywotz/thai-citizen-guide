import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Label } from "@/shared/components/ui/label";
import { Ban, Copy, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  listAPIKeys,
  createAPIKey,
  updateAPIKey,
  revokeAPIKey,
  deleteAPIKey,
  type APIKey,
  type APIKeyStatus,
  type CreatedAPIKey,
} from "@/features/api-keys/apiKeyApi";
import { useAuth } from "@/features/auth/useAuth";
import { API_KEY_STATUS_META as STATUS_META } from "@/shared/constants/status";

export default function ApiKeysPage() {
  const queryClient = useQueryClient();
  const { isReadOnly } = useAuth();

  const { data: keys = [], isLoading } = useQuery({
    queryKey: ["apiKeys"],
    queryFn: listAPIKeys,
  });

  // Create
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createExpiresInDays, setCreateExpiresInDays] = useState("");
  const [createRateLimit, setCreateRateLimit] = useState("");
  const [newKey, setNewKey] = useState<CreatedAPIKey | null>(null);
  const resetCreateForm = useCallback(() => {
    setCreateName("");
    setCreateExpiresInDays("");
    setCreateRateLimit("");
  }, []);
  const createMutation = useMutation({
    mutationFn: () => {
      const expiresInDays = createExpiresInDays.trim();
      const rateLimit = createRateLimit.trim();
      return createAPIKey({
        name: createName.trim(),
        ...(expiresInDays ? { expires_in_days: Number(expiresInDays) } : {}),
        ...(rateLimit ? { rate_limit_rpm: Number(rateLimit) } : {}),
      });
    },
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["apiKeys"] });
      setCreateOpen(false);
      resetCreateForm();
      setNewKey(created);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Revoke
  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeAPIKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["apiKeys"] });
      toast.success("เพิกถอน API Key เรียบร้อย");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleRevoke = useCallback(
    (key: APIKey) => {
      if (window.confirm("เพิกถอนคีย์นี้? คีย์จะใช้งานไม่ได้อีกต่อไป")) {
        revokeMutation.mutate(key.id);
      }
    },
    [revokeMutation],
  );

  // Edit
  const [editTarget, setEditTarget] = useState<APIKey | null>(null);
  const [editName, setEditName] = useState("");
  const editMutation = useMutation({
    mutationFn: () => updateAPIKey(editTarget!.id, editName.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["apiKeys"] });
      toast.success("แก้ไขชื่อเรียบร้อย");
      setEditTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Delete
  const [deleteTarget, setDeleteTarget] = useState<APIKey | null>(null);
  const deleteMutation = useMutation({
    mutationFn: () => deleteAPIKey(deleteTarget!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["apiKeys"] });
      toast.success("ลบ API Key เรียบร้อย");
      setDeleteTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const openEdit = useCallback((key: APIKey) => {
    setEditTarget(key);
    setEditName(key.name);
  }, []);

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    toast.success("คัดลอกแล้ว");
  };

  return (
    <div className="p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">API Keys</h2>
        {!isReadOnly && (
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-1" />
            สร้าง API Key
          </Button>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      )}

      {!isLoading && (
        <div className="space-y-2">
          {keys.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-12">
              ยังไม่มี API Key กรุณาสร้างใหม่
            </p>
          )}
          {keys.map((k) => (
            <Card key={k.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-foreground truncate">{k.name}</p>
                      <span
                        className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_META[k.status].className}`}
                      >
                        {STATUS_META[k.status].label}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground font-mono mt-1">
                      {k.key_prefix}…
                    </p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      วันหมดอายุ{" "}
                      {k.expires_at
                        ? new Date(k.expires_at).toLocaleString("th-TH")
                        : "ไม่มีวันหมดอายุ"}
                    </p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      จำกัดอัตรา{" "}
                      {k.rate_limit_rpm != null ? `${k.rate_limit_rpm} ครั้ง/นาที` : "—"}
                    </p>
                    {k.last_used_at && (
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        ใช้ล่าสุด {new Date(k.last_used_at).toLocaleString("th-TH")}
                      </p>
                    )}
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      สร้างเมื่อ {new Date(k.created_at).toLocaleString("th-TH")}
                    </p>
                  </div>
                  {!isReadOnly && (
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => openEdit(k)}
                        className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                        aria-label="แก้ไข"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      {k.status !== "revoked" && (
                        <button
                          onClick={() => handleRevoke(k)}
                          disabled={revokeMutation.isPending}
                          className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors disabled:opacity-50"
                          aria-label="เพิกถอน"
                        >
                          <Ban className="h-3.5 w-3.5" />
                        </button>
                      )}
                      <button
                        onClick={() => setDeleteTarget(k)}
                        className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                        aria-label="ลบ"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={(o) => { setCreateOpen(o); if (!o) resetCreateForm(); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>สร้าง API Key ใหม่</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label htmlFor="create-name">ชื่อ</Label>
              <Input
                id="create-name"
                placeholder="เช่น Production, Dev, Testing"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && createName.trim()) createMutation.mutate(); }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-expires">หมดอายุใน (วัน)</Label>
              <Input
                id="create-expires"
                type="number"
                min={1}
                placeholder="เว้นว่างไว้หากไม่มีวันหมดอายุ"
                value={createExpiresInDays}
                onChange={(e) => setCreateExpiresInDays(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-rate-limit">จำกัดอัตรา (ครั้ง/นาที)</Label>
              <Input
                id="create-rate-limit"
                type="number"
                min={1}
                placeholder="เว้นว่างไว้หากไม่จำกัด"
                value={createRateLimit}
                onChange={(e) => setCreateRateLimit(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={createMutation.isPending}>
              ยกเลิก
            </Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={!createName.trim() || createMutation.isPending}
            >
              {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              สร้าง
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* New key reveal dialog — shown once after creation */}
      <Dialog open={!!newKey} onOpenChange={(o) => { if (!o) setNewKey(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>สร้าง API Key เรียบร้อย</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm text-amber-600 font-medium">
              คัดลอก API Key นี้ไว้ทันที คุณจะไม่สามารถดูได้อีกครั้ง
            </p>
            <div className="flex items-center gap-2 bg-muted rounded-md p-3">
              <code className="text-xs font-mono flex-1 break-all select-all">
                {newKey?.key}
              </code>
              <button
                onClick={() => newKey && copyKey(newKey.key)}
                className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors shrink-0"
                aria-label="คัดลอก"
              >
                <Copy className="h-4 w-4" />
              </button>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setNewKey(null)}>รับทราบ</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={!!editTarget} onOpenChange={(o) => { if (!o) setEditTarget(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>แก้ไขชื่อ API Key</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="edit-name">ชื่อ</Label>
            <Input
              id="edit-name"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && editName.trim()) editMutation.mutate(); }}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTarget(null)} disabled={editMutation.isPending}>
              ยกเลิก
            </Button>
            <Button
              onClick={() => editMutation.mutate()}
              disabled={!editName.trim() || editMutation.isPending}
            >
              {editMutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              บันทึก
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => { if (!o) setDeleteTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>ยืนยันการลบ</AlertDialogTitle>
            <AlertDialogDescription>
              ลบ API Key "{deleteTarget?.name}" หรือไม่? ไม่สามารถย้อนกลับได้
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>ยกเลิก</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              ลบ
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
