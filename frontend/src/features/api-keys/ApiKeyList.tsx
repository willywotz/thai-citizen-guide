import { Ban, Pencil, Trash2 } from "lucide-react";
import { Card, CardContent } from "@/shared/components/ui/card";
import { API_KEY_STATUS_META as STATUS_META } from "@/shared/constants/status";
import type { APIKey } from "./apiKeyApi";

interface Props {
  keys: APIKey[];
  revokePending: boolean;
  onEdit: (key: APIKey) => void;
  onRevoke: (key: APIKey) => void;
  onDelete: (key: APIKey) => void;
}

export function ApiKeyList({ keys, revokePending, onEdit, onRevoke, onDelete }: Props) {
  if (keys.length === 0) {
    return (
      <p className="text-center text-sm text-muted-foreground py-12">
        ยังไม่มี API Key กรุณาสร้างใหม่
      </p>
    );
  }

  return (
    <div className="space-y-2">
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
                {k.last_used_at && (
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    ใช้ล่าสุด {new Date(k.last_used_at).toLocaleString("th-TH")}
                  </p>
                )}
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  สร้างเมื่อ {new Date(k.created_at).toLocaleString("th-TH")}
                </p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => onEdit(k)}
                  className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                  aria-label="แก้ไข"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                {k.status !== "revoked" && (
                  <button
                    onClick={() => onRevoke(k)}
                    disabled={revokePending}
                    className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors disabled:opacity-50"
                    aria-label="เพิกถอน"
                  >
                    <Ban className="h-3.5 w-3.5" />
                  </button>
                )}
                <button
                  onClick={() => onDelete(k)}
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
  );
}
