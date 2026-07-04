import { Pencil, Trash2 } from "lucide-react";
import { Card, CardContent } from "@/shared/components/ui/card";
import type { LlmRoute } from "./llmRouteApi";

interface Props {
  routes: LlmRoute[];
  isReadOnly: boolean;
  onEdit: (route: LlmRoute) => void;
  onDelete: (route: LlmRoute) => void;
}

export function LlmRoutesList({ routes, isReadOnly, onEdit, onDelete }: Props) {
  if (routes.length === 0) {
    return (
      <p className="text-center text-sm text-muted-foreground py-12">
        ยังไม่มีเส้นทาง LLM กรุณาเพิ่มใหม่
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {routes.map((r) => (
        <Card key={r.id}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-foreground truncate">{r.purpose}</p>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      r.enabled
                        ? "bg-green-100 text-green-700"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {r.enabled ? "เปิดใช้งาน" : "ปิดใช้งาน"}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground font-mono mt-1 truncate">
                  {r.provider_name} · {r.model}
                </p>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  หมดเวลาเฉพาะเส้นทาง{" "}
                  {r.timeout_override != null
                    ? `${r.timeout_override}s`
                    : "ใช้ค่าเริ่มต้นของผู้ให้บริการ"}
                </p>
              </div>
              {!isReadOnly && (
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => onEdit(r)}
                    className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                    aria-label="แก้ไข"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => onDelete(r)}
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
  );
}
