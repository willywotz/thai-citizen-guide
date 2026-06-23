import { useState } from 'react';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/shared/components/ui/table';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import { ScrollText } from 'lucide-react';
import { useAuditLog } from './useAuditLog';
import { PAGE_SIZE as PAGE_SIZES } from '@/shared/constants/query';
import { usePaginatedFilter } from '@/shared/hooks/usePaginatedFilter';

const PAGE_SIZE = PAGE_SIZES.audit;

const ACTION_OPTIONS = [
  'agency.update',
  'agency.status_change',
  'agency.delete',
  'agency.add_owner',
  'settings.update',
  'user.create',
  'user.update',
  'user.deactivate',
  'user.activate',
  'api_key.revoke',
];

const OBJECT_TYPE_OPTIONS = ['agency', 'user', 'settings', 'api_key'];

const ALL = '__all__';

export default function AuditLogPage() {
  const [action, setAction] = useState<string>(ALL);
  const [objectType, setObjectType] = useState<string>(ALL);
  const [actor, setActor] = useState('');

  // resetKey changes whenever server-side filters change → hook resets page to 1
  const resetKey = `${action}|${objectType}|${actor}`;

  const { page, setPage } = usePaginatedFilter({
    items: [] as never[],
    pageSize: PAGE_SIZE,
    resetKey,
  });

  const offset = (page - 1) * PAGE_SIZE;

  const { data, isLoading, isError } = useAuditLog({
    action: action === ALL ? undefined : action,
    object_type: objectType === ALL ? undefined : objectType,
    actor: actor || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  const entries = data?.data ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasNext = page < totalPages;

  return (
    <div className="p-4 md:p-6 space-y-4">
      <div className="flex items-center gap-2">
        <ScrollText className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-semibold">บันทึกการตรวจสอบ</h1>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Select value={action} onValueChange={setAction}>
          <SelectTrigger className="w-56">
            <SelectValue placeholder="การกระทำทั้งหมด" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>การกระทำทั้งหมด</SelectItem>
            {ACTION_OPTIONS.map((a) => (
              <SelectItem key={a} value={a}>{a}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={objectType} onValueChange={setObjectType}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="ประเภทอ็อบเจกต์ทั้งหมด" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>ประเภททั้งหมด</SelectItem>
            {OBJECT_TYPE_OPTIONS.map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          placeholder="ค้นหาอีเมลผู้กระทำ..."
          value={actor}
          onChange={(e) => setActor(e.target.value)}
          className="max-w-xs"
        />
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-48">เวลา</TableHead>
            <TableHead>ผู้กระทำ</TableHead>
            <TableHead>การกระทำ</TableHead>
            <TableHead>อ็อบเจกต์</TableHead>
            <TableHead>รายละเอียด</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading && (
            <TableRow><TableCell colSpan={5}>กำลังโหลด...</TableCell></TableRow>
          )}
          {isError && !isLoading && (
            <TableRow><TableCell colSpan={5}>เกิดข้อผิดพลาดในการโหลดข้อมูล</TableCell></TableRow>
          )}
          {!isLoading && !isError && entries.length === 0 && (
            <TableRow><TableCell colSpan={5}>ไม่พบบันทึก</TableCell></TableRow>
          )}
          {entries.map((entry) => (
            <TableRow key={entry.id}>
              <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                {new Date(entry.created_at).toLocaleString('th-TH')}
              </TableCell>
              <TableCell>{entry.actor_email ?? 'ระบบ'}</TableCell>
              <TableCell>
                <Badge variant="secondary">{entry.action}</Badge>
              </TableCell>
              <TableCell className="text-xs">
                {entry.object_type
                  ? `${entry.object_type}${entry.object_id ? ` · ${entry.object_id.slice(0, 8)}` : ''}`
                  : '—'}
              </TableCell>
              <TableCell className="max-w-md truncate text-xs text-muted-foreground">
                {entry.detail ? JSON.stringify(entry.detail) : '—'}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {total > 0
            ? `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} จาก ${total}`
            : `0 รายการ`}
        </p>
        <div className="space-x-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            ก่อนหน้า
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasNext}
            onClick={() => setPage(page + 1)}
          >
            ถัดไป
          </Button>
        </div>
      </div>
    </div>
  );
}
