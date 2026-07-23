import { useEffect, useState } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Switch } from '@/shared/components/ui/switch';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import { toast } from 'sonner';
import type { ManagedUser, UserRole } from './userApi';
import { ROLE_LABEL, ROLE_ORDER } from './roleLabels';
import { useCreateUser, useUpdateUser } from './useUsers';
import { validateCreateMode } from './userForm';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When provided, the dialog is in edit mode. */
  user?: ManagedUser | null;
}

export function UserFormDialog({ open, onOpenChange, user }: Props) {
  const isEdit = Boolean(user);
  const createMut = useCreateUser();
  const updateMut = useUpdateUser();

  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState<UserRole>('user');
  const [sendInvite, setSendInvite] = useState(false);
  const [password, setPassword] = useState('');

  useEffect(() => {
    if (open) {
      setEmail(user?.email ?? '');
      setDisplayName(user?.displayName ?? '');
      setRole(user?.role ?? 'user');
      setSendInvite(false);
      setPassword('');
    }
  }, [open, user]);

  async function handleSubmit() {
    try {
      if (isEdit && user) {
        await updateMut.mutateAsync({ id: user.id, payload: { display_name: displayName || null, role } });
        toast.success('อัปเดตผู้ใช้เรียบร้อยแล้ว');
      } else {
        const err = validateCreateMode({ sendInvite, password });
        if (err) { toast.error(err); return; }
        const res = await createMut.mutateAsync({
          email,
          role,
          display_name: displayName || null,
          ...(sendInvite ? { send_invite: true } : { password }),
        });
        if (res.reset_token) {
          toast.message('สร้างผู้ใช้แล้ว — ส่งอีเมลไม่สำเร็จ', { description: `Reset token: ${res.reset_token}` });
        } else {
          toast.success(sendInvite ? 'สร้างผู้ใช้และส่งคำเชิญแล้ว' : 'สร้างผู้ใช้เรียบร้อยแล้ว');
        }
      }
      onOpenChange(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'เกิดข้อผิดพลาด');
    }
  }

  const pending = createMut.isPending || updateMut.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? 'แก้ไขผู้ใช้' : 'เพิ่มผู้ใช้ใหม่'}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">อีเมล</Label>
            <Input id="email" type="email" value={email} disabled={isEdit}
              onChange={(e) => setEmail(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="displayName">ชื่อที่แสดง</Label>
            <Input id="displayName" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label>บทบาท</Label>
            <Select value={role} onValueChange={(v) => setRole(v as UserRole)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {ROLE_ORDER.map((r) => (
                  <SelectItem key={r} value={r}>{ROLE_LABEL[r]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {!isEdit && (
            <>
              <div className="flex items-center justify-between">
                <Label htmlFor="sendInvite">ส่งคำเชิญทางอีเมล</Label>
                <Switch id="sendInvite" checked={sendInvite} onCheckedChange={setSendInvite} />
              </div>
              {!sendInvite && (
                <div className="space-y-2">
                  <Label htmlFor="password">รหัสผ่านเริ่มต้น</Label>
                  <Input id="password" type="password" value={password}
                    onChange={(e) => setPassword(e.target.value)} />
                </div>
              )}
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>ยกเลิก</Button>
          <Button onClick={handleSubmit} disabled={pending}>
            {isEdit ? 'บันทึก' : 'สร้าง'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
