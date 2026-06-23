import { Copy } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import type { CreatedAPIKey } from "./apiKeyApi";

interface Props {
  newKey: CreatedAPIKey | null;
  onClose: () => void;
}

export function RevealKeyDialog({ newKey, onClose }: Props) {
  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    toast.success("คัดลอกแล้ว");
  };

  return (
    <Dialog open={!!newKey} onOpenChange={(o) => { if (!o) onClose(); }}>
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
          <Button onClick={onClose}>รับทราบ</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
