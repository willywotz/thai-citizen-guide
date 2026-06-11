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
import { Copy, Eye, EyeOff, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { listAPIKeys, createAPIKey, updateAPIKey, deleteAPIKey, type APIKey } from "@/features/api-keys/apiKeyApi";

export default function ApiKeysPage() {
  const queryClient = useQueryClient();
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set());
  const toggleReveal = useCallback((id: string) => {
    setRevealedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const { data: keys = [], isLoading } = useQuery({
    queryKey: ["apiKeys"],
    queryFn: listAPIKeys,
  });

  // Create
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const createMutation = useMutation({
    mutationFn: () => createAPIKey(createName.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["apiKeys"] });
      toast.success("สร้าง API Key เรียบร้อย");
      setCreateOpen(false);
      setCreateName("");
    },
    onError: (e: Error) => toast.error(e.message),
  });

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

  const openEdit = (key: APIKey) => {
    setEditTarget(key);
    setEditName(key.name);
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    toast.success("คัดลอกแล้ว");
  };

  const maskKey = (key: string) => `${key.slice(0, 8)}${"•".repeat(24)}${key.slice(-4)}`;

  return (
    <div className="p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">API Keys</h2>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" />
          สร้าง API Key
        </Button>
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
                    <p className="text-sm font-medium text-foreground truncate">{k.name}</p>
                    <div className="flex items-center gap-1.5 mt-1">
                      <code className="text-xs text-muted-foreground font-mono truncate">
                        {revealedKeys.has(k.id) ? k.key : maskKey(k.key)}
                      </code>
                      <button
                        onClick={() => toggleReveal(k.id)}
                        className="p-0.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors shrink-0"
                        aria-label={revealedKeys.has(k.id) ? "ซ่อน" : "แสดง"}
                      >
                        {revealedKeys.has(k.id) ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                      </button>
                      <button
                        onClick={() => copyKey(k.key)}
                        className="p-0.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors shrink-0"
                        aria-label="คัดลอก"
                      >
                        <Copy className="h-3 w-3" />
                      </button>
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-1">
                      สร้างเมื่อ {new Date(k.created_at).toLocaleString("th-TH")}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => openEdit(k)}
                      className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                      aria-label="แก้ไข"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => setDeleteTarget(k)}
                      className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                      aria-label="ลบ"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={(o) => { setCreateOpen(o); if (!o) setCreateName(""); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>สร้าง API Key ใหม่</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="create-name">ชื่อ</Label>
            <Input
              id="create-name"
              placeholder="เช่น Production, Dev, Testing"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && createName.trim()) createMutation.mutate(); }}
            />
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
