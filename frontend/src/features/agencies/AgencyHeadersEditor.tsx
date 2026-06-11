import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Plus, Trash2 } from "lucide-react";
import type { ApiHeader } from "@/shared/types/agency";

interface Props {
  headers: ApiHeader[];
  onAdd: () => void;
  onUpdate: (index: number, field: keyof ApiHeader, value: string) => void;
  onRemove: (index: number) => void;
}

export function AgencyHeadersEditor({ headers, onAdd, onUpdate, onRemove }: Props) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Header</Label>
        <Button type="button" variant="ghost" size="sm" className="h-7 text-xs gap-1" onClick={onAdd}>
          <Plus className="h-3 w-3" /> เพิ่ม
        </Button>
      </div>
      {headers.map((h, i) => (
        <div key={i} className="flex gap-2 items-start">
          <Input
            value={h.name}
            onChange={(e) => onUpdate(i, "name", e.target.value)}
            placeholder="Name"
            className="h-8 text-xs flex-1"
          />
          <Input
            value={h.value}
            onChange={(e) => onUpdate(i, "value", e.target.value)}
            placeholder="Value"
            className="h-8 text-xs flex-1"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={() => onRemove(i)}
          >
            <Trash2 className="h-3.5 w-3.5 text-destructive" />
          </Button>
        </div>
      ))}
      {headers.length === 0 && (
        <p className="text-[11px] text-muted-foreground py-2">ยังไม่มี header — กดเพิ่ม</p>
      )}
    </div>
  );
}
