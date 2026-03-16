import { useState } from "react";
import { useApiKeys } from "@/hooks/useApiKeys";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Trash2, Copy, Eye, EyeOff, Key } from "lucide-react";
import { PERMISSION_GROUPS, type AppPermission } from "@/types/auth";

export default function ApiKeysPage() {
  const { keys, isLoading, createKey, revokeKey } = useApiKeys();
  const { hasPermission } = useAuth();
  const [showCreate, setShowCreate] = useState(false);
  const [newRawKey, setNewRawKey] = useState<string | null>(null);
  const [showRawKey, setShowRawKey] = useState(false);

  if (!hasPermission("api_keys.write.own")) {
    return (
      <div className="p-6 text-center text-muted-foreground">ไม่มีสิทธิ์สร้าง API Keys</div>
    );
  }

  const activeKeys = keys.filter((k) => !k.revokedAt);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">API Keys</h1>
          <p className="text-sm text-muted-foreground">จัดการ API Keys สำหรับการเข้าถึงแบบ programmatic</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4 mr-2" />
          สร้าง Key ใหม่
        </Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">กำลังโหลด...</p>
      ) : activeKeys.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center space-y-3">
            <Key className="h-10 w-10 mx-auto text-muted-foreground/50" />
            <p className="text-muted-foreground">ยังไม่มี API Keys</p>
            <Button variant="outline" onClick={() => setShowCreate(true)}>
              สร้าง Key แรก
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {activeKeys.map((key) => (
            <Card key={key.id}>
              <CardContent className="py-4 flex items-start justify-between gap-4">
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{key.name}</span>
                  </div>
                  <code className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                    {key.keyPrefix}...
                  </code>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {key.scopes.map((s) => (
                      <Badge key={s} variant="secondary" className="text-xs">{s}</Badge>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    สร้างเมื่อ {new Date(key.createdAt).toLocaleDateString("th-TH")}
                    {key.lastUsedAt && ` · ใช้ล่าสุด ${new Date(key.lastUsedAt).toLocaleDateString("th-TH")}`}
                    {key.expiresAt && ` · หมดอายุ ${new Date(key.expiresAt).toLocaleDateString("th-TH")}`}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="shrink-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                  onClick={() => revokeKey(key.id)}
                  title="ยกเลิก Key"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create dialog */}
      <CreateKeyDialog
        open={showCreate}
        onOpenChange={(open) => {
          setShowCreate(open);
          if (!open) setNewRawKey(null);
        }}
        onCreated={(rawKey) => {
          setShowCreate(false);
          setNewRawKey(rawKey);
          setShowRawKey(false);
        }}
        createKey={createKey}
      />

      {/* Show newly created raw key */}
      {newRawKey && (
        <Dialog open onOpenChange={() => setNewRawKey(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>API Key สร้างสำเร็จ</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded p-3">
                คัดลอก API Key นี้ทันที จะไม่สามารถดูได้อีกครั้ง
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs bg-muted px-3 py-2 rounded font-mono break-all">
                  {showRawKey ? newRawKey : "•".repeat(32)}
                </code>
                <Button variant="ghost" size="icon" onClick={() => setShowRawKey(!showRawKey)}>
                  {showRawKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    navigator.clipboard.writeText(newRawKey);
                    toast.success("คัดลอกแล้ว!");
                  }}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={() => setNewRawKey(null)}>เสร็จสิ้น</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

function CreateKeyDialog({
  open,
  onOpenChange,
  onCreated,
  createKey,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (rawKey: string) => void;
  createKey: (input: { name: string; scopes: AppPermission[]; expiresAt?: string | null }) => Promise<string | null>;
}) {
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<AppPermission[]>(["conversations.read.own", "agencies.read"]);
  const [loading, setLoading] = useState(false);

  const toggleScope = (scope: AppPermission) => {
    setScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  };

  const handleCreate = async () => {
    if (!name.trim()) { toast.error("กรุณากรอกชื่อ Key"); return; }
    setLoading(true);
    const rawKey = await createKey({ name, scopes });
    setLoading(false);
    if (rawKey) {
      setName("");
      setScopes(["conversations.read.own", "agencies.read"]);
      onCreated(rawKey);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>สร้าง API Key ใหม่</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1">
            <Label>ชื่อ Key</Label>
            <Input
              placeholder="เช่น CI/CD Pipeline, ระบบทดสอบ"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>สิทธิ์การเข้าถึง (Scopes)</Label>
            {Object.entries(PERMISSION_GROUPS).map(([group, groupScopes]) => (
              <div key={group}>
                <p className="text-xs font-medium text-muted-foreground mb-1">{group}</p>
                <div className="space-y-1">
                  {groupScopes.map((scope) => (
                    <label key={scope} className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={scopes.includes(scope)}
                        onChange={() => toggleScope(scope)}
                        className="rounded"
                      />
                      <code className="text-xs">{scope}</code>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>ยกเลิก</Button>
          <Button onClick={handleCreate} disabled={loading}>
            {loading ? "กำลังสร้าง..." : "สร้าง Key"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
