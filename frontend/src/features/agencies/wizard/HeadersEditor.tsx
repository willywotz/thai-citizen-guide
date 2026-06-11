import { Plus, X } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import type { ApiHeader } from "@/shared/types/agency";

interface Props {
  headers: ApiHeader[];
  onChange: (headers: ApiHeader[]) => void;
}

export function HeadersEditor({ headers, onChange }: Props) {
  const update = (i: number, field: keyof ApiHeader, value: string) => {
    onChange(headers.map((h, idx) => (idx === i ? { ...h, [field]: value } : h)));
  };

  return (
    <div className="space-y-2">
      {headers.map((h, i) => (
        <div key={i} className="flex gap-2">
          <Input placeholder="Header name" value={h.name} onChange={(e) => update(i, "name", e.target.value)} />
          <Input placeholder="Value" value={h.value} onChange={(e) => update(i, "value", e.target.value)} />
          <Button variant="ghost" size="icon" onClick={() => onChange(headers.filter((_, idx) => idx !== i))}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button variant="outline" size="sm" onClick={() => onChange([...headers, { name: "", value: "" }])}>
        <Plus className="h-3.5 w-3.5 mr-1" /> เพิ่ม header
      </Button>
    </div>
  );
}
