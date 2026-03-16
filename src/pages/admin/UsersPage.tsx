import { useState } from "react";
import { useUserManagement } from "@/hooks/useUserManagement";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, UserX, UserCheck } from "lucide-react";
import { ROLE_LABELS, ROLE_COLORS, type AppRole } from "@/types/auth";

const ALL_ROLES: AppRole[] = ["super_admin", "admin", "moderator", "user", "api_user"];

export default function UsersPage() {
  const { isSuperAdmin, hasPermission } = useAuth();
  const { users, total, isLoading, search, setSearch, assignRole, removeRole, toggleActive } =
    useUserManagement();

  if (!hasPermission("users.read")) {
    return (
      <div className="p-6 text-center text-muted-foreground">ไม่มีสิทธิ์เข้าถึงหน้านี้</div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">จัดการผู้ใช้</h1>
        <p className="text-sm text-muted-foreground">ผู้ใช้ทั้งหมด {total} คน</p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="ค้นหาด้วยชื่อหรืออีเมล..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">กำลังโหลด...</p>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-3 font-medium">ผู้ใช้</th>
                <th className="text-left px-4 py-3 font-medium">สิทธิ์</th>
                <th className="text-left px-4 py-3 font-medium">เข้าสู่ระบบล่าสุด</th>
                <th className="text-left px-4 py-3 font-medium">การดำเนินการ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {users.map((u) => {
                const initials = ((u.profile?.displayName || u.email || "U")
                  .split(" ")
                  .map((w) => w[0])
                  .join("")
                  .slice(0, 2)
                  .toUpperCase());
                const isActive = (u.profile as any)?.is_active !== false;

                return (
                  <tr key={u.id} className={!isActive ? "opacity-50" : undefined}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Avatar className="h-8 w-8">
                          <AvatarFallback className="text-xs bg-primary/10 text-primary">
                            {initials}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-medium leading-none">
                            {u.profile?.displayName || "—"}
                          </p>
                          <p className="text-xs text-muted-foreground">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {u.roles.map((role) => (
                          <span
                            key={role}
                            className={`text-xs px-2 py-0.5 rounded-full border font-medium ${ROLE_COLORS[role as AppRole]}`}
                          >
                            {ROLE_LABELS[role as AppRole]}
                          </span>
                        ))}
                        {hasPermission("users.roles.assign") && (
                          <RoleAssignSelect
                            currentRoles={u.roles as AppRole[]}
                            isSuperAdmin={isSuperAdmin}
                            onAssign={(role) => assignRole(u.id, role)}
                            onRemove={(role) => removeRole(u.id, role)}
                          />
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {u.last_sign_in_at
                        ? new Date(u.last_sign_in_at).toLocaleDateString("th-TH")
                        : "ไม่เคย"}
                    </td>
                    <td className="px-4 py-3">
                      {hasPermission("users.write") && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className={isActive ? "text-destructive hover:bg-destructive/10" : "text-green-700 hover:bg-green-50"}
                          onClick={() => toggleActive(u.id, isActive)}
                        >
                          {isActive ? (
                            <><UserX className="h-3.5 w-3.5 mr-1" /> ระงับ</>
                          ) : (
                            <><UserCheck className="h-3.5 w-3.5 mr-1" /> เปิดใช้</>
                          )}
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function RoleAssignSelect({
  currentRoles,
  isSuperAdmin,
  onAssign,
  onRemove,
}: {
  currentRoles: AppRole[];
  isSuperAdmin: boolean;
  onAssign: (role: AppRole) => void;
  onRemove: (role: AppRole) => void;
}) {
  const availableToAssign = ALL_ROLES.filter((r) => {
    if (!isSuperAdmin && (r === "super_admin" || r === "admin")) return false;
    return !currentRoles.includes(r);
  });

  if (availableToAssign.length === 0) return null;

  return (
    <Select onValueChange={(v) => onAssign(v as AppRole)}>
      <SelectTrigger className="h-6 w-28 text-xs border-dashed">
        <SelectValue placeholder="+ เพิ่ม" />
      </SelectTrigger>
      <SelectContent>
        {availableToAssign.map((role) => (
          <SelectItem key={role} value={role} className="text-xs">
            {ROLE_LABELS[role]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
