import { Loader2 } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import type { UseMutationResult } from "@tanstack/react-query";
import type { CreatedAPIKey } from "./apiKeyApi";

interface Props {
  open: boolean;
  name: string;
  expiresInDays: string;
  mutation: UseMutationResult<CreatedAPIKey, Error, void>;
  onNameChange: (v: string) => void;
  onExpiresInDaysChange: (v: string) => void;
  onClose: () => void;
}

export function CreateApiKeyDialog({
  open,
  name,
  expiresInDays,
  mutation,
  onNameChange,
  onExpiresInDaysChange,
  onClose,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
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
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) mutation.mutate(); }}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="create-expires">หมดอายุใน (วัน)</Label>
            <Input
              id="create-expires"
              type="number"
              min={1}
              placeholder="เว้นว่างไว้หากไม่มีวันหมดอายุ"
              value={expiresInDays}
              onChange={(e) => onExpiresInDaysChange(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={mutation.isPending}>
            ยกเลิก
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={!name.trim() || mutation.isPending}
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
            สร้าง
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
