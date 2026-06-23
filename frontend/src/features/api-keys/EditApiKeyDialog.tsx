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
import type { APIKey } from "./apiKeyApi";

interface Props {
  target: APIKey | null;
  name: string;
  mutation: UseMutationResult<APIKey, Error, { id: string; name: string }>;
  onNameChange: (v: string) => void;
  onSave: () => void;
  onClose: () => void;
}

export function EditApiKeyDialog({ target, name, mutation, onNameChange, onSave, onClose }: Props) {
  return (
    <Dialog open={!!target} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>แก้ไขชื่อ API Key</DialogTitle>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="edit-name">ชื่อ</Label>
          <Input
            id="edit-name"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) onSave(); }}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={mutation.isPending}>
            ยกเลิก
          </Button>
          <Button
            onClick={onSave}
            disabled={!name.trim() || mutation.isPending}
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
            บันทึก
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
