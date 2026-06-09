# Frontend Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the frontend from a layer-based structure to a feature-based structure, decompose four large page files into focused components, and clean up data fetching imports.

**Architecture:** All feature code (pages, components, hooks, API, types) lives in `src/features/<feature>/`. Shared infrastructure (ui components, layout, lib, hooks, types) lives in `src/shared/`. All hooks already use React Query — this refactor is primarily a file reorganization plus component extraction.

**Tech Stack:** React 18, TypeScript, Vite, TanStack Query v5, React Router v6, shadcn/ui, Tailwind CSS, Vitest

---

## Prerequisite — check out a new branch

```bash
cd frontend
git checkout -b refactor/frontend-feature-structure
```

---

## Task 1: Scaffold the directory structure

**Files:** Create directories only — no file contents yet.

- [ ] **Step 1: Create all feature + shared directories**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src
mkdir -p features/agencies features/api-keys features/architecture \
         features/auth features/chat features/connection-logs \
         features/dashboard features/executive features/health \
         features/heatmap features/history features/insights \
         features/public features/settings \
         shared/components/layout shared/components/ui \
         shared/hooks shared/lib shared/types shared/data
```

- [ ] **Step 2: Verify structure**

```bash
find /mnt/c/Users/foo/thai-citizen-guide/frontend/src/features \
     /mnt/c/Users/foo/thai-citizen-guide/frontend/src/shared -type d
```
Expected: all 14 feature dirs and 6 shared dirs listed.

- [ ] **Step 3: Commit scaffold**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add frontend/src/features frontend/src/shared
git commit -m "chore: scaffold feature and shared directory structure"
```

---

## Task 2: Move shared infrastructure

Move `lib/`, `data/`, `types/`, shared UI + layout components, and shared hooks into `shared/`.

**Files:**
- Move: `src/lib/apiClient.ts` → `src/shared/lib/apiClient.ts`
- Move: `src/lib/utils.ts` → `src/shared/lib/utils.ts`
- Move: `src/data/mockData.ts` → `src/shared/data/mockData.ts`
- Move: `src/types/*.ts` → `src/shared/types/*.ts`
- Move: `src/components/ui/*` → `src/shared/components/ui/`
- Move: `src/components/NavLink.tsx` → `src/shared/components/NavLink.tsx`
- Move: `src/components/ThemeProvider.tsx` → `src/shared/components/ThemeProvider.tsx`
- Move: `src/components/ThemeToggle.tsx` → `src/shared/components/ThemeToggle.tsx`
- Move: `src/components/layout/AppLayout.tsx` → `src/shared/components/layout/AppLayout.tsx`
- Move: `src/components/layout/AppSidebar.tsx` → `src/shared/components/layout/AppSidebar.tsx`
- Move: `src/hooks/use-mobile.tsx` → `src/shared/hooks/use-mobile.tsx`
- Move: `src/hooks/use-toast.ts` → `src/shared/hooks/use-toast.ts`

- [ ] **Step 1: Move files with git mv**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

git mv lib/apiClient.ts shared/lib/apiClient.ts
git mv lib/utils.ts shared/lib/utils.ts
git mv data/mockData.ts shared/data/mockData.ts

git mv types/agency.ts shared/types/agency.ts
git mv types/chat.ts shared/types/chat.ts
git mv types/connectionLog.ts shared/types/connectionLog.ts
git mv types/conversation.ts shared/types/conversation.ts
git mv types/dashboard.ts shared/types/dashboard.ts
git mv types/index.ts shared/types/index.ts
git mv types/settings.ts shared/types/settings.ts

git mv components/ui shared/components/ui
git mv components/NavLink.tsx shared/components/NavLink.tsx
git mv components/ThemeProvider.tsx shared/components/ThemeProvider.tsx
git mv components/ThemeToggle.tsx shared/components/ThemeToggle.tsx
git mv components/layout/AppLayout.tsx shared/components/layout/AppLayout.tsx
git mv components/layout/AppSidebar.tsx shared/components/layout/AppSidebar.tsx

git mv hooks/use-mobile.tsx shared/hooks/use-mobile.tsx
git mv hooks/use-toast.ts shared/hooks/use-toast.ts
```

- [ ] **Step 2: Global find-and-replace for shared import paths**

Run each of the following `sed` commands from `frontend/src/`:

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

# lib/
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/lib/apiClient'|from '@/shared/lib/apiClient'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/lib/utils'|from '@/shared/lib/utils'|g"

# data/
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/data/mockData'|from '@/shared/data/mockData'|g"

# types/
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/types/agency'|from '@/shared/types/agency'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/types/chat'|from '@/shared/types/chat'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/types/connectionLog'|from '@/shared/types/connectionLog'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/types/conversation'|from '@/shared/types/conversation'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/types/settings'|from '@/shared/types/settings'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/types'|from '@/shared/types'|g"

# components/ui/ — pages that import @/components/ui/... need updating:
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/ui/|from '@/shared/components/ui/|g"

# shared layout + standalone components
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/NavLink'|from '@/shared/components/NavLink'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/ThemeProvider'|from '@/shared/components/ThemeProvider'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/ThemeToggle'|from '@/shared/components/ThemeToggle'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/layout/AppLayout'|from '@/shared/components/layout/AppLayout'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/layout/AppSidebar'|from '@/shared/components/layout/AppSidebar'|g"

# shared hooks
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/hooks/use-mobile'|from '@/shared/hooks/use-mobile'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/hooks/use-toast'|from '@/shared/hooks/use-toast'|g"
```

- [ ] **Step 3: TypeScript check — expect errors (old paths remain for feature files)**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend
pnpm exec tsc --noEmit --project tsconfig.app.json 2>&1 | head -30
```

Expected: errors about `@/hooks/...`, `@/services/...`, `@/pages/...`, `@/components/agencies/...` — these will be fixed in subsequent tasks. Errors about `@/lib/`, `@/types/`, `@/components/ui/` should be zero at this point.

- [ ] **Step 4: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "refactor: move shared infrastructure to src/shared/"
```

---

## Task 3: Move auth feature

**Files:**
- Move: `src/pages/LoginPage.tsx` → `src/features/auth/LoginPage.tsx`
- Move: `src/pages/SignupPage.tsx` → `src/features/auth/SignupPage.tsx`
- Move: `src/pages/ForgotPasswordPage.tsx` → `src/features/auth/ForgotPasswordPage.tsx`
- Move: `src/pages/ResetPasswordPage.tsx` → `src/features/auth/ResetPasswordPage.tsx`
- Move: `src/components/auth/ProtectedRoute.tsx` → `src/features/auth/ProtectedRoute.tsx`
- Move: `src/hooks/useAuth.tsx` → `src/features/auth/useAuth.tsx`

- [ ] **Step 1: Move auth files**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

git mv pages/LoginPage.tsx features/auth/LoginPage.tsx
git mv pages/SignupPage.tsx features/auth/SignupPage.tsx
git mv pages/ForgotPasswordPage.tsx features/auth/ForgotPasswordPage.tsx
git mv pages/ResetPasswordPage.tsx features/auth/ResetPasswordPage.tsx
git mv components/auth/ProtectedRoute.tsx features/auth/ProtectedRoute.tsx
git mv hooks/useAuth.tsx features/auth/useAuth.tsx
```

- [ ] **Step 2: Update imports referencing auth**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/hooks/useAuth'|from '@/features/auth/useAuth'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/auth/ProtectedRoute'|from '@/features/auth/ProtectedRoute'|g"
```

- [ ] **Step 3: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "refactor: move auth feature to src/features/auth/"
```

---

## Task 4: Move agencies feature

**Files:**
- Move: `src/pages/AgenciesPage.tsx` → `src/features/agencies/AgenciesPage.tsx`
- Move: `src/pages/AgencyDetailPage.tsx` → `src/features/agencies/AgencyDetailPage.tsx`
- Move: `src/components/agencies/ConnectionTestResult.tsx` → `src/features/agencies/ConnectionTestResult.tsx`
- Move: `src/hooks/useAgencies.ts` → `src/features/agencies/useAgencies.ts`
- Move: `src/services/agencyApi.ts` → `src/features/agencies/agencyApi.ts`

- [ ] **Step 1: Move agencies files**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

git mv pages/AgenciesPage.tsx features/agencies/AgenciesPage.tsx
git mv pages/AgencyDetailPage.tsx features/agencies/AgencyDetailPage.tsx
git mv components/agencies/ConnectionTestResult.tsx features/agencies/ConnectionTestResult.tsx
git mv hooks/useAgencies.ts features/agencies/useAgencies.ts
git mv services/agencyApi.ts features/agencies/agencyApi.ts
```

- [ ] **Step 2: Update imports**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/hooks/useAgencies'|from '@/features/agencies/useAgencies'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/services/agencyApi'|from '@/features/agencies/agencyApi'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/agencies/ConnectionTestResult'|from '@/features/agencies/ConnectionTestResult'|g"
```

- [ ] **Step 3: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "refactor: move agencies feature to src/features/agencies/"
```

---

## Task 5: Extract AgencyDetailPage sub-components

Break `AgencyDetailPage.tsx` (439 lines) into 5 focused components.

**Files:**
- Create: `src/features/agencies/AgencyDetailHeader.tsx`
- Create: `src/features/agencies/AgencyDetailStats.tsx`
- Create: `src/features/agencies/AgencyConnectionLogsTab.tsx`
- Create: `src/features/agencies/AgencyStatsTab.tsx`
- Create: `src/features/agencies/AgencyInfoTab.tsx`
- Modify: `src/features/agencies/AgencyDetailPage.tsx`

- [ ] **Step 1: Create AgencyDetailHeader.tsx**

```tsx
// src/features/agencies/AgencyDetailHeader.tsx
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { ArrowLeft, Wifi, Loader2 } from "lucide-react";
import type { Agency } from "@/shared/types";
import type { TestResult } from "./ConnectionTestResult";
import type { UseMutationResult } from "@tanstack/react-query";

const connectionTypeColors: Record<string, string> = {
  MCP: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  API: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  A2A: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

interface Props {
  agency: Agency;
  testMutation: UseMutationResult<TestResult, Error, { agencyId: string }>;
  onBack: () => void;
  onTestConnection: () => void;
}

export function AgencyDetailHeader({ agency, testMutation, onBack, onTestConnection }: Props) {
  return (
    <div className="flex items-center gap-4">
      <Button variant="ghost" size="icon" onClick={onBack}>
        <ArrowLeft className="h-5 w-5" />
      </Button>
      <div className="flex items-center gap-3 flex-1">
        <div
          className="w-14 h-14 rounded-xl flex items-center justify-center text-3xl"
          style={{ backgroundColor: `${agency.color}15` }}
        >
          {agency.logo}
        </div>
        <div>
          <h1 className="text-xl font-semibold text-foreground">{agency.name}</h1>
          <p className="text-sm text-muted-foreground">{agency.description}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {agency.endpointUrl && (
          <Button variant="outline" size="sm" className="gap-1.5" onClick={onTestConnection} disabled={testMutation.isPending}>
            {testMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wifi className="h-3.5 w-3.5" />}
            ทดสอบการเชื่อมต่อ
          </Button>
        )}
        <Badge className={connectionTypeColors[agency.connectionType] || ""}>{agency.connectionType}</Badge>
        <Badge
          className={
            agency.status === "active"
              ? "bg-green-100 text-green-700 hover:bg-green-100 dark:bg-green-900/30 dark:text-green-400"
              : "bg-red-100 text-red-700 hover:bg-red-100 dark:bg-red-900/30 dark:text-red-400"
          }
        >
          {agency.status === "active" ? "Active" : "Inactive"}
        </Badge>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create AgencyDetailStats.tsx**

```tsx
// src/features/agencies/AgencyDetailStats.tsx
import { Card, CardContent } from "@/shared/components/ui/card";
import { Activity, CheckCircle2, Clock, XCircle } from "lucide-react";
import type { Agency } from "@/shared/types";

interface Stats {
  successRate: number;
  avgLatency: number;
  error: number;
}

interface Props {
  agency: Agency;
  stats: Stats;
}

export function AgencyDetailStats({ agency, stats }: Props) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
            <Activity className="h-3.5 w-3.5" /> การเรียกใช้ทั้งหมด
          </div>
          <p className="text-2xl font-bold text-foreground">{agency.totalCalls.toLocaleString()}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
            <CheckCircle2 className="h-3.5 w-3.5" /> อัตราสำเร็จ
          </div>
          <p className="text-2xl font-bold text-foreground">{stats.successRate}%</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
            <Clock className="h-3.5 w-3.5" /> ค่าเฉลี่ย Latency (24 ชม.)
          </div>
          <p className="text-2xl font-bold text-foreground">{stats.avgLatency} ms</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
            <XCircle className="h-3.5 w-3.5" /> ข้อผิดพลาด
          </div>
          <p className="text-2xl font-bold text-foreground">{stats.error}</p>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Create AgencyConnectionLogsTab.tsx**

```tsx
// src/features/agencies/AgencyConnectionLogsTab.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { Badge } from "@/shared/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/components/ui/table";
import { format } from "date-fns";
import type { ConnectionLogResponse } from "@/features/connection-logs/useConnectionLogs";

const statusColors: Record<string, string> = {
  success: "text-green-600 dark:text-green-400",
  error: "text-destructive",
};

interface Props {
  logs: ConnectionLogResponse;
  logsLoading: boolean;
}

export function AgencyConnectionLogsTab({ logs, logsLoading }: Props) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">ประวัติการเชื่อมต่อล่าสุด</CardTitle>
      </CardHeader>
      <CardContent>
        {logsLoading ? (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : logs.total_connections === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">ยังไม่มีประวัติการเชื่อมต่อ</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[140px]">เวลา</TableHead>
                <TableHead className="w-[80px]">ประเภท</TableHead>
                <TableHead className="w-[80px]">สถานะ</TableHead>
                <TableHead className="w-[100px]">Latency</TableHead>
                <TableHead>รายละเอียด</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.items.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="text-xs font-mono text-muted-foreground">
                    {format(new Date(log.created_at), "dd/MM HH:mm:ss")}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[10px]">{log.action}</Badge>
                  </TableCell>
                  <TableCell>
                    <span className={`text-xs font-medium ${statusColors[log.status] || ""}`}>
                      {log.status === "success" ? "✓ สำเร็จ" : "✗ ล้มเหลว"}
                    </span>
                  </TableCell>
                  <TableCell className="text-xs font-mono">{log.latency_ms} ms</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{log.detail}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Create AgencyStatsTab.tsx**

```tsx
// src/features/agencies/AgencyStatsTab.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";

interface HourlyBucket { time: string; count: number }
interface StatusSlice { name: string; value: number; color: string }

interface Props {
  hourlyData: HourlyBucket[];
  statusPieData: StatusSlice[];
}

export function AgencyStatsTab({ hourlyData, statusPieData }: Props) {
  return (
    <div className="grid md:grid-cols-2 gap-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">การเรียกใช้ตามช่วงเวลา</CardTitle>
        </CardHeader>
        <CardContent>
          {hourlyData.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">ไม่มีข้อมูล</p>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={hourlyData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} className="fill-muted-foreground" />
                <YAxis tick={{ fontSize: 10 }} className="fill-muted-foreground" />
                <Tooltip />
                <Bar dataKey="count" fill="hsl(213, 70%, 45%)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">สัดส่วนสถานะ</CardTitle>
        </CardHeader>
        <CardContent>
          {statusPieData.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">ไม่มีข้อมูล</p>
          ) : (
            <div className="flex items-center justify-center">
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={statusPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {statusPieData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 5: Create AgencyInfoTab.tsx**

```tsx
// src/features/agencies/AgencyInfoTab.tsx
import { Card, CardContent } from "@/shared/components/ui/card";
import { Badge } from "@/shared/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/components/ui/table";
import type { Agency } from "@/shared/types";

interface Props { agency: Agency }

export function AgencyInfoTab({ agency }: Props) {
  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-muted-foreground mb-1">ชื่อย่อ</p>
            <p className="text-sm font-medium text-foreground">{agency.shortName}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">ประเภทการเชื่อมต่อ</p>
            <p className="text-sm font-medium text-foreground">{agency.connectionType}</p>
          </div>
          <div className="md:col-span-2">
            <p className="text-xs text-muted-foreground mb-1">Endpoint URL</p>
            <p className="text-sm font-mono text-foreground break-all">{agency.endpointUrl || "-"}</p>
          </div>

          {agency.connectionType === "API" && (
            <>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Auth Method</p>
                <p className="text-sm font-medium text-foreground">{agency.authMethod || "api_key"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Auth Header</p>
                <p className="text-sm font-mono text-foreground">{agency.authHeader || "-"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Base Path</p>
                <p className="text-sm font-mono text-foreground">{agency.basePath || "-"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Rate Limit</p>
                <p className="text-sm font-medium text-foreground">{agency.rateLimitRpm ? `${agency.rateLimitRpm} RPM` : "-"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Request Format</p>
                <p className="text-sm font-medium text-foreground uppercase">{agency.requestFormat || "json"}</p>
              </div>
              {agency.apiEndpoints && agency.apiEndpoints.length > 0 && (
                <div className="md:col-span-2">
                  <p className="text-xs text-muted-foreground mb-2">API Endpoints ({agency.apiEndpoints.length})</p>
                  <div className="border border-border rounded-md overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[80px] text-xs">Method</TableHead>
                          <TableHead className="text-xs">Path</TableHead>
                          <TableHead className="text-xs">คำอธิบาย</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {agency.apiEndpoints.map((ep, i) => (
                          <TableRow key={i}>
                            <TableCell><Badge variant="outline" className="text-[10px] font-mono">{ep.method}</Badge></TableCell>
                            <TableCell className="text-xs font-mono">{ep.path}</TableCell>
                            <TableCell className="text-xs text-muted-foreground">{ep.description}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
              {agency.responseSchema && agency.responseSchema.length > 0 && (
                <div className="md:col-span-2">
                  <p className="text-xs text-muted-foreground mb-2">Response Schema ({agency.responseSchema.length} fields)</p>
                  <div className="border border-border rounded-md overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs">Field</TableHead>
                          <TableHead className="w-[80px] text-xs">Type</TableHead>
                          <TableHead className="text-xs">คำอธิบาย</TableHead>
                          <TableHead className="text-xs">ตัวอย่าง</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {agency.responseSchema.map((f, i) => (
                          <TableRow key={i}>
                            <TableCell className="text-xs font-mono text-foreground">{f.field}</TableCell>
                            <TableCell><Badge variant="outline" className="text-[10px] font-mono">{f.type}</Badge></TableCell>
                            <TableCell className="text-xs text-muted-foreground">{f.description}</TableCell>
                            <TableCell className="text-xs font-mono text-muted-foreground">{f.example || "-"}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
            </>
          )}

          <div className="md:col-span-2">
            <p className="text-xs text-muted-foreground mb-1.5">ขอบเขตข้อมูล</p>
            <div className="flex flex-wrap gap-1.5">
              {agency.dataScope.map((scope, i) => (
                <span key={i} className="text-[11px] bg-accent text-accent-foreground px-2.5 py-1 rounded-full">
                  {scope}
                </span>
              ))}
            </div>
          </div>
          {agency.apiKeyName && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">API Key Name</p>
              <p className="text-sm font-mono text-foreground">{agency.apiKeyName}</p>
            </div>
          )}
          {agency.expectedPayload && (
            <div className="md:col-span-2">
              <p className="text-xs text-muted-foreground mb-1.5">Expected Payload</p>
              <pre className="text-xs font-mono bg-muted rounded-md p-3 overflow-x-auto border border-border whitespace-pre-wrap break-all">
                {JSON.stringify(agency.expectedPayload, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 6: Rewrite AgencyDetailPage.tsx as thin orchestrator**

Replace the full contents of `src/features/agencies/AgencyDetailPage.tsx` with:

```tsx
// src/features/agencies/AgencyDetailPage.tsx
import { useParams, useNavigate } from "react-router-dom";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { Button } from "@/shared/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { ArrowLeft, Wifi, BarChart3, Activity } from "lucide-react";
import { useMemo } from "react";
import { format } from "date-fns";
import { useAgencies, useTestConnection } from "./useAgencies";
import { useConnectionLogs } from "@/features/connection-logs/useConnectionLogs";
import { ConnectionTestResult } from "./ConnectionTestResult";
import { AgencyDetailHeader } from "./AgencyDetailHeader";
import { AgencyDetailStats } from "./AgencyDetailStats";
import { AgencyConnectionLogsTab } from "./AgencyConnectionLogsTab";
import { AgencyStatsTab } from "./AgencyStatsTab";
import { AgencyInfoTab } from "./AgencyInfoTab";

export default function AgencyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: agencies = [], isLoading: agenciesLoading } = useAgencies();
  const { data: logs, isLoading: logsLoading } = useConnectionLogs({ agencyId: id });
  const testMutation = useTestConnection();

  const agency = agencies.find((a) => a.id === id);

  const stats = useMemo(() => {
    if (!logs) return { total: 0, success: 0, error: 0, avgLatency: 0, successRate: 0 };
    const success = logs.successful_connections;
    const error = logs.failed_connections;
    return {
      total: logs.total_connections,
      success,
      error,
      avgLatency: logs.average_latency_ms,
      successRate: logs.total_connections > 0 ? Math.round((success / logs.total_connections) * 100) : 0,
    };
  }, [logs]);

  const hourlyData = useMemo(() => {
    const buckets: Record<string, number> = {};
    logs.items.forEach((l) => {
      const hour = format(new Date(l.created_at), "MM/dd HH:00");
      buckets[hour] = (buckets[hour] || 0) + 1;
    });
    return Object.entries(buckets)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-12)
      .map(([time, count]) => ({ time, count }));
  }, [logs]);

  const statusPieData = useMemo(() => [
    { name: "สำเร็จ", value: stats.success, color: "hsl(152, 55%, 42%)" },
    { name: "ล้มเหลว", value: stats.error, color: "hsl(0, 72%, 55%)" },
  ].filter((d) => d.value > 0), [stats]);

  if (agenciesLoading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!agency) {
    return (
      <div className="p-4 md:p-6 text-center space-y-4">
        <p className="text-muted-foreground">ไม่พบหน่วยงาน</p>
        <Button variant="outline" onClick={() => navigate("/agencies")}>
          <ArrowLeft className="h-4 w-4 mr-2" /> กลับ
        </Button>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <AgencyDetailHeader
        agency={agency}
        testMutation={testMutation}
        onBack={() => navigate("/agencies")}
        onTestConnection={() => testMutation.mutateAsync({ agencyId: agency.id })}
      />

      {(testMutation.isPending || testMutation.data || testMutation.isError) && (
        <ConnectionTestResult
          result={testMutation.data ?? (testMutation.isError
            ? { success: false, protocol: agency.connectionType, version: '-', steps: [], latency: '0ms', error: testMutation.error?.message ?? 'Request failed' }
            : null)}
          loading={testMutation.isPending}
        />
      )}

      <AgencyDetailStats agency={agency} stats={stats} />

      <Tabs defaultValue="logs" className="space-y-4">
        <TabsList>
          <TabsTrigger value="logs"><Wifi className="h-4 w-4 mr-1.5" /> Connection Logs</TabsTrigger>
          <TabsTrigger value="stats"><BarChart3 className="h-4 w-4 mr-1.5" /> สถิติ</TabsTrigger>
          <TabsTrigger value="info"><Activity className="h-4 w-4 mr-1.5" /> ข้อมูลหน่วยงาน</TabsTrigger>
        </TabsList>
        <TabsContent value="logs">
          <AgencyConnectionLogsTab logs={logs} logsLoading={logsLoading} />
        </TabsContent>
        <TabsContent value="stats">
          <AgencyStatsTab hourlyData={hourlyData} statusPieData={statusPieData} />
        </TabsContent>
        <TabsContent value="info">
          <AgencyInfoTab agency={agency} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

- [ ] **Step 7: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "refactor: extract AgencyDetailPage sub-components"
```

---

## Task 6: Move chat feature

**Files:**
- Move: `src/pages/ChatPage.tsx` → `src/features/chat/ChatPage.tsx`
- Move: `src/components/chat/AgentStepDisplay.tsx` → `src/features/chat/AgentStepDisplay.tsx`
- Move: `src/components/chat/FeedbackDialog.tsx` → `src/features/chat/FeedbackDialog.tsx`
- Move: `src/components/chat/MessageBubble.tsx` → `src/features/chat/MessageBubble.tsx`
- Move: `src/hooks/useChat.ts` → `src/features/chat/useChat.ts`
- Move: `src/hooks/useChatHistory.ts` → `src/features/history/useChatHistory.ts` *(goes to history — it fetches conversation history)*
- Move: `src/hooks/useConversationMessages.ts` → `src/features/history/useConversationMessages.ts`
- Move: `src/services/chatApi.ts` → `src/features/chat/chatApi.ts`
- Move: `src/services/feedbackApi.ts` → `src/features/chat/feedbackApi.ts`

- [ ] **Step 1: Move chat and history hook files**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

git mv pages/ChatPage.tsx features/chat/ChatPage.tsx
git mv components/chat/AgentStepDisplay.tsx features/chat/AgentStepDisplay.tsx
git mv components/chat/FeedbackDialog.tsx features/chat/FeedbackDialog.tsx
git mv components/chat/MessageBubble.tsx features/chat/MessageBubble.tsx
git mv hooks/useChat.ts features/chat/useChat.ts
git mv hooks/useChatHistory.ts features/history/useChatHistory.ts
git mv hooks/useConversationMessages.ts features/history/useConversationMessages.ts
git mv services/chatApi.ts features/chat/chatApi.ts
git mv services/feedbackApi.ts features/chat/feedbackApi.ts
```

- [ ] **Step 2: Update imports**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/hooks/useChat'|from '@/features/chat/useChat'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/hooks/useChatHistory'|from '@/features/history/useChatHistory'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/hooks/useConversationMessages'|from '@/features/history/useConversationMessages'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/services/chatApi'|from '@/features/chat/chatApi'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/services/feedbackApi'|from '@/features/chat/feedbackApi'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/chat/AgentStepDisplay'|from '@/features/chat/AgentStepDisplay'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/chat/FeedbackDialog'|from '@/features/chat/FeedbackDialog'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/chat/MessageBubble'|from '@/features/chat/MessageBubble'|g"
```

- [ ] **Step 3: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "refactor: move chat and history hooks to feature folders"
```

---

## Task 7: Move dashboard feature + extract sub-components

**Files:**
- Move: `src/pages/DashboardPage.tsx` → `src/features/dashboard/DashboardPage.tsx`
- Move: `src/components/dashboard/FeedbackAnalytics.tsx` → `src/features/dashboard/FeedbackAnalytics.tsx`
- Move: `src/components/dashboard/LiveActivityChart.tsx` → `src/features/dashboard/LiveActivityChart.tsx`
- Move: `src/hooks/useDashboard.ts` → `src/features/dashboard/useDashboard.ts`
- Move: `src/hooks/useRealtimeActivity.ts` → `src/features/dashboard/useRealtimeActivity.ts`
- Move: `src/services/dashboardApi.ts` → `src/features/dashboard/dashboardApi.ts`
- Create: `src/features/dashboard/DashboardStatsRow.tsx`
- Create: `src/features/dashboard/DashboardAgencyStatus.tsx`

- [ ] **Step 1: Move dashboard files**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

git mv pages/DashboardPage.tsx features/dashboard/DashboardPage.tsx
git mv components/dashboard/FeedbackAnalytics.tsx features/dashboard/FeedbackAnalytics.tsx
git mv components/dashboard/LiveActivityChart.tsx features/dashboard/LiveActivityChart.tsx
git mv hooks/useDashboard.ts features/dashboard/useDashboard.ts
git mv hooks/useRealtimeActivity.ts features/dashboard/useRealtimeActivity.ts
git mv services/dashboardApi.ts features/dashboard/dashboardApi.ts
```

- [ ] **Step 2: Update imports**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/hooks/useDashboard'|from '@/features/dashboard/useDashboard'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/hooks/useRealtimeActivity'|from '@/features/dashboard/useRealtimeActivity'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/services/dashboardApi'|from '@/features/dashboard/dashboardApi'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/dashboard/FeedbackAnalytics'|from '@/features/dashboard/FeedbackAnalytics'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/components/dashboard/LiveActivityChart'|from '@/features/dashboard/LiveActivityChart'|g"
```

- [ ] **Step 3: Create DashboardStatsRow.tsx**

```tsx
// src/features/dashboard/DashboardStatsRow.tsx
import { Card, CardContent } from "@/shared/components/ui/card";
import { cn } from "@/shared/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCard {
  label: string;
  value: string;
  icon: LucideIcon;
  color: string;
}

interface Props {
  statCards: StatCard[];
}

export function DashboardStatsRow({ statCards }: Props) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {statCards.map((s, i) => (
        <Card
          key={i}
          className={cn(
            "group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 animate-fade-in",
          )}
          style={{ animationDelay: `${i * 80}ms`, animationFillMode: "both" }}
        >
          <CardContent className="p-4 relative z-10">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-muted-foreground font-medium">{s.label}</span>
              <div className={cn("p-2 rounded-lg bg-muted/80 transition-colors group-hover:bg-primary/10", s.color)}>
                <s.icon className="h-4 w-4" />
              </div>
            </div>
            <p className="text-2xl font-bold text-foreground tracking-tight">{s.value}</p>
          </CardContent>
          <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.03] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        </Card>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Create DashboardAgencyStatus.tsx**

```tsx
// src/features/dashboard/DashboardAgencyStatus.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { cn } from "@/shared/lib/utils";
import type { Agency } from "@/shared/types";

interface Props { agencies: Agency[] }

export function DashboardAgencyStatus({ agencies }: Props) {
  return (
    <Card className="animate-fade-in" style={{ animationDelay: "560ms", animationFillMode: "both" }}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">สถานะการเชื่อมต่อหน่วยงาน</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2.5">
          {agencies.map((a, i) => (
            <div
              key={a.id}
              className="flex items-center justify-between p-3 bg-muted/40 rounded-lg border border-border/50 hover:bg-muted/70 hover:border-border transition-all duration-200 animate-fade-in"
              style={{ animationDelay: `${600 + i * 60}ms`, animationFillMode: "both" }}
            >
              <div className="flex items-center gap-3">
                <div className="text-xl w-9 h-9 rounded-lg bg-card flex items-center justify-center shadow-sm border border-border/50">
                  {a.logo}
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">{a.shortName}</p>
                  <p className="text-[10px] text-muted-foreground">{a.connectionType} Protocol</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-muted-foreground">{a.totalCalls?.toLocaleString()} calls</span>
                <span className={cn(
                  "text-[10px] font-medium px-2.5 py-1 rounded-full flex items-center gap-1",
                  a.status === 'active' ? 'bg-success/10 text-success' : 'bg-destructive/10 text-destructive'
                )}>
                  <span className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    a.status === 'active' ? 'bg-success animate-pulse' : 'bg-destructive'
                  )} />
                  {a.status === 'active' ? 'Online' : 'Offline'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: Rewrite DashboardPage.tsx as thin orchestrator**

Replace the full contents of `src/features/dashboard/DashboardPage.tsx` with:

```tsx
// src/features/dashboard/DashboardPage.tsx
import { useState, useEffect, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area,
} from "recharts";
import { MessageSquare, TrendingUp, Clock, ThumbsUp, Loader2, Activity } from "lucide-react";
import { useDashboardStats, useAgencyUsage, useWeeklyTrend, useCategoryData } from "./useDashboard";
import { useAgencies } from "@/features/agencies/useAgencies";
import { cn } from "@/shared/lib/utils";
import { useTheme } from "next-themes";
import { FeedbackAnalytics } from "./FeedbackAnalytics";
import { DashboardStatsRow } from "./DashboardStatsRow";
import { DashboardAgencyStatus } from "./DashboardAgencyStatus";

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-card px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-foreground">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} className="text-xs text-muted-foreground">
          {p.name}: <span className="font-semibold text-foreground">{p.value?.toLocaleString()}</span>
        </p>
      ))}
    </div>
  );
};

export default function DashboardPage() {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const { data: stats, isLoading: statsLoading, dataUpdatedAt } = useDashboardStats();
  const { data: agencyUsage } = useAgencyUsage();
  const { data: weeklyTrend } = useWeeklyTrend();
  const { data: categoryStats } = useCategoryData();
  const { data: agencies = [] } = useAgencies();

  const chartColors = useMemo(() => ({
    grid: isDark ? "hsl(220 15% 25%)" : "hsl(214 25% 92%)",
    tick: isDark ? "hsl(215 15% 60%)" : "hsl(215 15% 50%)",
    primary: isDark ? "hsl(213 65% 60%)" : "hsl(213 70% 45%)",
    dotStroke: isDark ? "hsl(220 18% 14%)" : "white",
    palette: isDark
      ? ["hsl(145 50% 50%)", "hsl(213 65% 60%)", "hsl(25 80% 60%)", "hsl(280 45% 60%)"]
      : ["hsl(145 55% 40%)", "hsl(213 70% 45%)", "hsl(25 85% 55%)", "hsl(280 50% 50%)"],
  }), [isDark]);

  const [lastUpdated, setLastUpdated] = useState("");
  useEffect(() => {
    if (dataUpdatedAt) {
      setLastUpdated(new Date(dataUpdatedAt).toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    }
  }, [dataUpdatedAt]);

  const totalUsage = agencyUsage?.reduce((sum, a) => sum + a.value, 0) || 1;

  const statCards = stats ? [
    { label: "คำถามทั้งหมด", value: stats.totalQuestions.toLocaleString(), icon: MessageSquare, color: "text-primary" },
    { label: "คำถามวันนี้", value: stats.todayQuestions.toLocaleString(), icon: TrendingUp, color: "text-success" },
    { label: "เวลาตอบเฉลี่ย", value: `${stats.avgResponseTime}s`, icon: Clock, color: "text-warning" },
    { label: "ความพึงพอใจ", value: `${stats.satisfactionRate}%`, icon: ThumbsUp, color: "text-info" },
  ] : [];

  if (statsLoading) {
    return (
      <div className="flex items-center justify-center h-[50vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex items-center justify-between animate-fade-in">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Dashboard สถิติการใช้งาน</h2>
          <p className="text-xs text-muted-foreground mt-0.5">ภาพรวมการใช้งานระบบ AI ประสานงานภาครัฐ</p>
        </div>
        {lastUpdated && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted/50 px-3 py-1.5 rounded-full">
            <Activity className="h-3 w-3 text-success animate-pulse" />
            <span>Live</span>
            <span className="text-muted-foreground/60">•</span>
            <span>{lastUpdated}</span>
          </div>
        )}
      </div>

      <DashboardStatsRow statCards={statCards} />

      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="animate-fade-in" style={{ animationDelay: "320ms", animationFillMode: "both" }}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">แนวโน้มการใช้งานรายสัปดาห์</CardTitle>
              <span className="text-[10px] text-muted-foreground bg-muted px-2 py-1 rounded-full">7 วันล่าสุด</span>
            </div>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={weeklyTrend} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradientQuestions" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={chartColors.primary} stopOpacity={isDark ? 0.25 : 0.3} />
                    <stop offset="95%" stopColor={chartColors.primary} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: chartColors.tick }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: chartColors.tick }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="questions" name="คำถาม" stroke={chartColors.primary}
                  strokeWidth={2.5} fill="url(#gradientQuestions)"
                  dot={{ r: 4, fill: chartColors.primary, stroke: chartColors.dotStroke, strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: chartColors.primary, stroke: chartColors.dotStroke, strokeWidth: 2 }}
                  animationDuration={1200} animationEasing="ease-out"
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="animate-fade-in" style={{ animationDelay: "400ms", animationFillMode: "both" }}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">สัดส่วนการเรียกใช้หน่วยงาน</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="55%" height={220}>
                <PieChart>
                  <Pie data={agencyUsage} dataKey="value" nameKey="name" cx="50%" cy="50%"
                    outerRadius={85} innerRadius={55} paddingAngle={3} cornerRadius={4}
                    animationDuration={1000} animationEasing="ease-out"
                  >
                    {agencyUsage?.map((_, i) => (
                      <Cell key={i} fill={chartColors.palette[i % chartColors.palette.length]} stroke="none" />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2.5">
                {agencyUsage?.map((entry, i) => (
                  <div key={i} className="group">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: chartColors.palette[i % chartColors.palette.length] }} />
                        <span className="text-foreground font-medium">{entry.name}</span>
                      </div>
                      <span className="text-muted-foreground">{((entry.value / totalUsage) * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden ml-[18px]">
                      <div className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${(entry.value / totalUsage) * 100}%`, backgroundColor: chartColors.palette[i % chartColors.palette.length] }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="animate-fade-in" style={{ animationDelay: "480ms", animationFillMode: "both" }}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">หมวดหมู่คำถามยอดนิยม</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={categoryStats} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: chartColors.tick }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="category" width={110} tick={{ fontSize: 11, fill: chartColors.tick }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" name="จำนวน" radius={[0, 6, 6, 0]} animationDuration={1000} animationEasing="ease-out">
                  {categoryStats?.map((_, i) => (
                    <Cell key={i} fill={chartColors.palette[i % chartColors.palette.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <DashboardAgencyStatus agencies={agencies} />
      </div>

      <FeedbackAnalytics />
    </div>
  );
}
```

- [ ] **Step 6: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "refactor: move dashboard feature and extract sub-components"
```

---

## Task 8: Move executive feature + extract sub-components

**Files:**
- Move: `src/pages/ExecutivePage.tsx` → `src/features/executive/ExecutivePage.tsx`
- Move: `src/hooks/useExecutive.ts` → `src/features/executive/useExecutive.ts`
- Move: `src/services/executiveApi.ts` → `src/features/executive/executiveApi.ts`
- Create: `src/features/executive/ExecutiveKpiGrid.tsx`
- Create: `src/features/executive/ExecutiveTrendChart.tsx`
- Create: `src/features/executive/ExecutiveWeeklyBrief.tsx`

- [ ] **Step 1: Move executive files**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

git mv pages/ExecutivePage.tsx features/executive/ExecutivePage.tsx
git mv hooks/useExecutive.ts features/executive/useExecutive.ts
git mv services/executiveApi.ts features/executive/executiveApi.ts
```

- [ ] **Step 2: Update imports**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/hooks/useExecutive'|from '@/features/executive/useExecutive'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/services/executiveApi'|from '@/features/executive/executiveApi'|g"
```

- [ ] **Step 3: Create ExecutiveKpiGrid.tsx**

```tsx
// src/features/executive/ExecutiveKpiGrid.tsx
import { Card, CardContent } from "@/shared/components/ui/card";
import { TrendingUp, TrendingDown, Users } from "lucide-react";

interface Kpis {
  thisMonthQuestions: number;
  lastMonthQuestions: number;
  momGrowthQuestions: number;
  thisYearQuestions: number;
  lastYearQuestions: number;
  yoyGrowthQuestions: number;
  thisMonthCitizens: number;
  lastMonthCitizens: number;
  momGrowthCitizens: number;
  thisYearCitizens: number;
  lastYearCitizens: number;
  yoyGrowthCitizens: number;
}

function StatCard({ label, value, sublabel, trend }: { label: string; value: string; sublabel?: string; trend?: number }) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground font-medium">{label}</p>
            <p className="text-2xl font-bold">{value}</p>
            {sublabel && <p className="text-xs text-muted-foreground">{sublabel}</p>}
          </div>
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <Users className="h-5 w-5" />
          </div>
        </div>
        {trend !== undefined && (
          <div className="mt-3 flex items-center gap-1 text-xs">
            {trend >= 0 ? <TrendingUp className="h-3 w-3 text-success" /> : <TrendingDown className="h-3 w-3 text-destructive" />}
            <span className={trend >= 0 ? 'text-success font-semibold' : 'text-destructive font-semibold'}>
              {trend >= 0 ? '+' : ''}{trend}%
            </span>
            <span className="text-muted-foreground">เทียบกับเดือนก่อน</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface Props { kpis: Kpis }

export function ExecutiveKpiGrid({ kpis }: Props) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard label="คำถามรวมเดือนนี้" value={kpis.thisMonthQuestions.toLocaleString()} sublabel={`${kpis.lastMonthQuestions.toLocaleString()} คำถามในเดือนก่อน`} trend={kpis.momGrowthQuestions} />
      <StatCard label="คำถามรวมปีนี้" value={kpis.thisYearQuestions.toLocaleString()} sublabel={`${kpis.lastYearQuestions.toLocaleString()} คำถามในปีก่อน`} trend={kpis.yoyGrowthQuestions} />
      <StatCard label="ประชาชนที่ได้รับบริการเดือนนี้" value={kpis.thisMonthCitizens.toLocaleString()} sublabel={`${kpis.lastMonthCitizens.toLocaleString()} คนในเดือนก่อน`} trend={kpis.momGrowthCitizens} />
      <StatCard label="ประชาชนที่ได้รับบริการปีนี้" value={kpis.thisYearCitizens.toLocaleString()} sublabel={`${kpis.lastYearCitizens.toLocaleString()} คนในปีก่อน`} trend={kpis.yoyGrowthCitizens} />
    </div>
  );
}
```

- [ ] **Step 4: Create ExecutiveTrendChart.tsx**

```tsx
// src/features/executive/ExecutiveTrendChart.tsx
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";

interface MonthPoint { month: string; questions: number; satisfaction: number }
interface Props { monthlyTrend: MonthPoint[] }

export function ExecutiveTrendChart({ monthlyTrend }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">แนวโน้ม 12 เดือนย้อนหลัง</CardTitle>
        <CardDescription>จำนวนคำถามและความพึงพอใจ</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={monthlyTrend}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" />
            <YAxis yAxisId="left" stroke="hsl(var(--muted-foreground))" />
            <YAxis yAxisId="right" orientation="right" stroke="hsl(var(--muted-foreground))" domain={[80, 100]} />
            <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }} />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="questions" stroke="hsl(var(--primary))" strokeWidth={2} name="คำถาม" dot={{ r: 4 }} />
            <Line yAxisId="right" type="monotone" dataKey="satisfaction" stroke="hsl(var(--success))" strokeWidth={2} name="ความพึงพอใจ %" dot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: Create ExecutiveWeeklyBrief.tsx**

```tsx
// src/features/executive/ExecutiveWeeklyBrief.tsx
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface Props { weeklyBrief: string | null }

export function ExecutiveWeeklyBrief({ weeklyBrief }: Props) {
  return (
    <Card className="border bg-white">
      <CardHeader>
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-primary/10">
            <Sparkles className="h-5 w-5 text-primary" />
          </div>
          <div>
            <CardTitle className="text-lg">AI Weekly Executive Brief</CardTitle>
            <CardDescription>วิเคราะห์โดย AI สำหรับผู้บริหาร</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="prose prose-sm dark:prose-invert max-w-none text-foreground">
          {weeklyBrief ? (
            <ReactMarkdown>{weeklyBrief}</ReactMarkdown>
          ) : (
            <p className="text-muted-foreground">กำลังสร้างรายงานสรุป...</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 6: Rewrite ExecutivePage.tsx as thin orchestrator**

Replace the full contents of `src/features/executive/ExecutivePage.tsx`:

```tsx
// src/features/executive/ExecutivePage.tsx
import { useExecutiveSummary } from "./useExecutive";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { AlertCircle } from "lucide-react";
import { ExecutiveKpiGrid } from "./ExecutiveKpiGrid";
import { ExecutiveTrendChart } from "./ExecutiveTrendChart";
import { ExecutiveWeeklyBrief } from "./ExecutiveWeeklyBrief";

export default function ExecutivePage() {
  const { data, isLoading, error, refetch } = useExecutiveSummary();

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-12 w-96" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32" />)}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6">
        <Card className="border-destructive/50">
          <CardContent className="p-8 text-center space-y-3">
            <AlertCircle className="h-10 w-10 mx-auto text-destructive" />
            <p className="font-semibold">ไม่สามารถโหลดข้อมูลผู้บริหารได้</p>
            <Button onClick={() => refetch()} variant="outline">ลองอีกครั้ง</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { kpis, monthlyTrend, weeklyBrief, generatedAt } = data;

  return (
    <div className="p-6 space-y-6 mx-auto">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight portal-gradient-text">Executive Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            ภาพรวมเชิงกลยุทธ์สำหรับผู้บริหาร · อัปเดตล่าสุด {new Date(generatedAt).toLocaleString('th-TH')}
          </p>
        </div>
      </div>
      <ExecutiveKpiGrid kpis={kpis} />
      <ExecutiveTrendChart monthlyTrend={monthlyTrend} />
      <ExecutiveWeeklyBrief weeklyBrief={weeklyBrief} />
    </div>
  );
}
```

- [ ] **Step 7: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "refactor: move executive feature and extract sub-components"
```

---

## Task 9: Move connection-logs feature + extract sub-components

**Files:**
- Move: `src/pages/ConnectionLogsPage.tsx` → `src/features/connection-logs/ConnectionLogsPage.tsx`
- Move: `src/hooks/useConnectionLogs.ts` → `src/features/connection-logs/useConnectionLogs.ts`
- Create: `src/features/connection-logs/ConnectionLogStats.tsx`
- Create: `src/features/connection-logs/ConnectionLogFilters.tsx`
- Create: `src/features/connection-logs/ConnectionLogsTable.tsx`

- [ ] **Step 1: Move connection-logs files**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

git mv pages/ConnectionLogsPage.tsx features/connection-logs/ConnectionLogsPage.tsx
git mv hooks/useConnectionLogs.ts features/connection-logs/useConnectionLogs.ts
```

- [ ] **Step 2: Update imports**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/hooks/useConnectionLogs'|from '@/features/connection-logs/useConnectionLogs'|g"
```

- [ ] **Step 3: Create ConnectionLogStats.tsx**

```tsx
// src/features/connection-logs/ConnectionLogStats.tsx
import type { ConnectionLogInfo } from "./useConnectionLogs";

interface Props { logInfo: ConnectionLogInfo | undefined }

export function ConnectionLogStats({ logInfo }: Props) {
  const items = [
    { label: "ทั้งหมด", value: logInfo?.total_connections ?? 0, color: "text-foreground" },
    { label: "สำเร็จ", value: logInfo?.successful_connections ?? 0, color: "text-green-600 dark:text-green-400" },
    { label: "ล้มเหลว", value: logInfo?.failed_connections ?? 0, color: "text-destructive" },
    { label: "Latency เฉลี่ย (24 ชม.)", value: `${logInfo?.average_latency_ms ?? 0} ms`, color: "text-foreground" },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {items.map((s) => (
        <div key={s.label} className="border rounded-lg p-3 bg-card">
          <p className="text-xs text-muted-foreground">{s.label}</p>
          <p className={`text-xl font-semibold ${s.color}`}>{s.value}</p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Create ConnectionLogFilters.tsx**

```tsx
// src/features/connection-logs/ConnectionLogFilters.tsx
import { Input } from "@/shared/components/ui/input";
import { Button } from "@/shared/components/ui/button";
import { Search, X } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import type { Agency } from "@/shared/types";

interface Props {
  search: string;
  filterStatus: string | null;
  filterType: string | null;
  filterAgency: string | null;
  agencies: Agency[];
  hasFilters: boolean;
  onSearchChange: (v: string) => void;
  onStatusChange: (v: string | null) => void;
  onTypeChange: (v: string | null) => void;
  onAgencyChange: (v: string | null) => void;
  onReset: () => void;
}

export function ConnectionLogFilters({
  search, filterStatus, filterType, filterAgency, agencies, hasFilters,
  onSearchChange, onStatusChange, onTypeChange, onAgencyChange, onReset,
}: Props) {
  return (
    <div className="flex flex-wrap gap-2 items-center">
      <div className="relative flex-1 min-w-[180px]">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="ค้นหา detail..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9 h-8 text-sm"
        />
      </div>
      <div className="flex gap-1">
        {([null, "success", "error"] as const).map((s) => (
          <button
            key={s ?? "all"}
            onClick={() => onStatusChange(s)}
            className={cn(
              "text-xs px-3 py-1.5 rounded-full border transition-colors",
              filterStatus === s ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:bg-accent"
            )}
          >
            {s === null ? "ทั้งหมด" : s === "success" ? "สำเร็จ" : "ล้มเหลว"}
          </button>
        ))}
      </div>
      <div className="flex gap-1">
        {["MCP", "API", "A2A"].map((t) => (
          <button
            key={t}
            onClick={() => onTypeChange(filterType === t ? null : t)}
            className={cn(
              "text-xs px-3 py-1.5 rounded-full border transition-colors",
              filterType === t ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:bg-accent"
            )}
          >
            {t}
          </button>
        ))}
      </div>
      {agencies.length > 0 && (
        <select
          value={filterAgency ?? ""}
          onChange={(e) => onAgencyChange(e.target.value || null)}
          className="text-xs h-8 px-2 rounded-md border border-border bg-background text-foreground"
        >
          <option value="">หน่วยงานทั้งหมด</option>
          {agencies.map((a) => <option key={a.id} value={a.id}>{a.shortName}</option>)}
        </select>
      )}
      {hasFilters && (
        <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground" onClick={onReset}>
          <X className="h-3.5 w-3.5 mr-1" /> ล้างตัวกรอง
        </Button>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create ConnectionLogsTable.tsx**

```tsx
// src/features/connection-logs/ConnectionLogsTable.tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { Button } from "@/shared/components/ui/button";
import { CheckCircle2, XCircle, Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/shared/lib/utils";
import type { ConnectionLog } from "@/shared/types/connectionLog";

const connectionTypeColors: Record<string, string> = {
  MCP: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  API: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  A2A: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

interface Props {
  items: ConnectionLog[];
  isLoading: boolean;
  agencyMap: Record<string, string>;
  selectedLog: ConnectionLog | null;
  onSelectLog: (log: ConnectionLog) => void;
  onCloseLog: () => void;
  page: number;
  totalPages: number;
  totalItems: number;
  onPageChange: (p: number) => void;
}

export function ConnectionLogsTable({
  items, isLoading, agencyMap, selectedLog, onSelectLog, onCloseLog,
  page, totalPages, totalItems, onPageChange,
}: Props) {
  return (
    <>
      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[130px]">วันที่/เวลา</TableHead>
                <TableHead>หน่วยงาน</TableHead>
                <TableHead className="w-[80px]">ประเภท</TableHead>
                <TableHead className="w-[70px]">Action</TableHead>
                <TableHead className="w-[80px]">สถานะ</TableHead>
                <TableHead className="w-[80px] text-right">Latency</TableHead>
                <TableHead>รายละเอียด</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-10 text-sm">ไม่พบข้อมูล</TableCell>
                </TableRow>
              ) : items.map((log) => (
                <TableRow key={log.id} className="cursor-pointer hover:bg-accent/50" onClick={() => onSelectLog(log)}>
                  <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                    {format(new Date(log.created_at), "dd/MM/yy HH:mm:ss")}
                  </TableCell>
                  <TableCell className="text-xs font-medium whitespace-nowrap">
                    {agencyMap[log.agency_id] || (log.agency_id ? log.agency_id.slice(0, 8) : "—")}
                  </TableCell>
                  <TableCell className="text-xs whitespace-nowrap">
                    <span className={cn("text-[10px] px-2 py-0.5 rounded-full font-medium", connectionTypeColors[log.connection_type] || "bg-muted text-muted-foreground")}>
                      {log.connection_type}
                    </span>
                  </TableCell>
                  <TableCell className="text-xs capitalize text-muted-foreground whitespace-nowrap">{log.action}</TableCell>
                  <TableCell className="text-xs whitespace-nowrap">
                    {log.status === "success" ? (
                      <span className="flex items-center gap-1 text-green-600 dark:text-green-400 text-xs"><CheckCircle2 className="h-3.5 w-3.5" /> สำเร็จ</span>
                    ) : (
                      <span className="flex items-center gap-1 text-destructive text-xs"><XCircle className="h-3.5 w-3.5" /> ล้มเหลว</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-right tabular-nums whitespace-nowrap">
                    <span className={cn(log.latency_ms > 1000 ? "text-amber-600" : "text-muted-foreground")}>{log.latency_ms} ms</span>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate whitespace-nowrap" title={log.detail}>{log.detail || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs text-muted-foreground">หน้า {page}/{totalPages} · {totalItems} รายการ</span>
          <div className="flex items-center gap-1">
            <Button variant="outline" size="icon" className="h-7 w-7" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              const p = totalPages <= 7 ? i + 1 : page <= 4 ? i + 1 : page >= totalPages - 3 ? totalPages - 6 + i : page - 3 + i;
              return (
                <Button key={p} variant={p === page ? "default" : "outline"} size="icon" className="h-7 w-7 text-xs" onClick={() => onPageChange(p)}>{p}</Button>
              );
            })}
            <Button variant="outline" size="icon" className="h-7 w-7" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      <Dialog open={!!selectedLog} onOpenChange={(o) => { if (!o) onCloseLog(); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm">
              {selectedLog?.status === "success" ? <CheckCircle2 className="h-4 w-4 text-green-600" /> : <XCircle className="h-4 w-4 text-destructive" />}
              Connection Log Detail
            </DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div><p className="text-xs text-muted-foreground">วันที่/เวลา</p><p className="font-medium text-xs">{format(selectedLog.created_at, "dd/MM/yyyy HH:mm:ss")}</p></div>
                <div><p className="text-xs text-muted-foreground">หน่วยงาน</p><p className="font-medium text-xs">{agencyMap[selectedLog.agency_id] || selectedLog.agency_id || "—"}</p></div>
                <div>
                  <p className="text-xs text-muted-foreground">ประเภทการเชื่อมต่อ</p>
                  <span className={cn("text-[10px] px-2 py-0.5 rounded-full font-medium", connectionTypeColors[selectedLog.connection_type] || "bg-muted text-muted-foreground")}>{selectedLog.connection_type}</span>
                </div>
                <div><p className="text-xs text-muted-foreground">Action</p><p className="font-medium text-xs capitalize">{selectedLog.action}</p></div>
                <div>
                  <p className="text-xs text-muted-foreground">สถานะ</p>
                  {selectedLog.status === "success"
                    ? <span className="flex items-center gap-1 text-green-600 dark:text-green-400 text-xs font-medium"><CheckCircle2 className="h-3.5 w-3.5" /> สำเร็จ</span>
                    : <span className="flex items-center gap-1 text-destructive text-xs font-medium"><XCircle className="h-3.5 w-3.5" /> ล้มเหลว</span>}
                </div>
                <div><p className="text-xs text-muted-foreground">Latency</p><p className={cn("font-medium text-xs", selectedLog.latency_ms > 15_000 ? "text-amber-600" : "")}>{selectedLog.latency_ms} ms</p></div>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">รายละเอียด</p>
                <pre className="text-xs bg-muted rounded-md p-3 whitespace-pre-wrap break-all font-mono leading-relaxed max-h-48 overflow-y-auto">{selectedLog.detail || "—"}</pre>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
```

- [ ] **Step 6: Rewrite ConnectionLogsPage.tsx as thin orchestrator**

Replace the full contents of `src/features/connection-logs/ConnectionLogsPage.tsx`:

```tsx
// src/features/connection-logs/ConnectionLogsPage.tsx
import { useState, useMemo } from "react";
import { Button } from "@/shared/components/ui/button";
import { Activity, RefreshCw } from "lucide-react";
import { useConnectionLogs, useConnectionLogInfo } from "./useConnectionLogs";
import { useAgencies } from "@/features/agencies/useAgencies";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/shared/lib/utils";
import type { ConnectionLog } from "@/shared/types/connectionLog";
import { ConnectionLogStats } from "./ConnectionLogStats";
import { ConnectionLogFilters } from "./ConnectionLogFilters";
import { ConnectionLogsTable } from "./ConnectionLogsTable";

const PAGE_SIZE = 20;

export default function ConnectionLogsPage() {
  const queryClient = useQueryClient();
  const { data: agencies = [] } = useAgencies();

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [filterStatus, setFilterStatus] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string | null>(null);
  const [filterAgency, setFilterAgency] = useState<string | null>(null);
  const [selectedLog, setSelectedLog] = useState<ConnectionLog | null>(null);

  const { data: logInfo } = useConnectionLogInfo();
  const { data, isLoading, isFetching } = useConnectionLogs({ page, limit: PAGE_SIZE, search });

  const items = data?.items ?? [];
  const totalItems = data?.total_items ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));

  const agencyMap = useMemo(
    () => Object.fromEntries(agencies.map((a) => [a.id, a.shortName])),
    [agencies]
  );

  const filtered = useMemo(() => items.filter((log) => {
    if (filterStatus && log.status !== filterStatus) return false;
    if (filterType && log.connection_type !== filterType) return false;
    if (filterAgency && log.agency_id !== filterAgency) return false;
    return true;
  }), [items, filterStatus, filterType, filterAgency]);

  const hasFilters = !!(filterStatus || filterType || filterAgency || search);

  const resetFilters = () => {
    setFilterStatus(null);
    setFilterType(null);
    setFilterAgency(null);
    setSearch("");
    setPage(1);
  };

  return (
    <div className="p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold text-foreground">ประวัติการเชื่อมต่อ</h2>
        </div>
        <Button variant="outline" size="sm" onClick={() => queryClient.invalidateQueries({ queryKey: ["connection-logs"] })} disabled={isFetching}>
          <RefreshCw className={cn("h-3.5 w-3.5 mr-1", isFetching && "animate-spin")} /> รีเฟรช
        </Button>
      </div>

      <ConnectionLogStats logInfo={logInfo} />

      <ConnectionLogFilters
        search={search} filterStatus={filterStatus} filterType={filterType}
        filterAgency={filterAgency} agencies={agencies} hasFilters={hasFilters}
        onSearchChange={(v) => { setSearch(v); setPage(1); }}
        onStatusChange={setFilterStatus}
        onTypeChange={setFilterType}
        onAgencyChange={setFilterAgency}
        onReset={resetFilters}
      />

      <ConnectionLogsTable
        items={filtered} isLoading={isLoading} agencyMap={agencyMap}
        selectedLog={selectedLog} onSelectLog={setSelectedLog} onCloseLog={() => setSelectedLog(null)}
        page={page} totalPages={totalPages} totalItems={totalItems} onPageChange={setPage}
      />
    </div>
  );
}
```

- [ ] **Step 7: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "refactor: move connection-logs feature and extract sub-components"
```

---

## Task 10: Move remaining page features

**Files (all moves, no extractions):**
- Move: `src/pages/HistoryPage.tsx` → `src/features/history/HistoryPage.tsx`
- Move: `src/services/historyApi.ts` → `src/features/history/historyApi.ts`
- Move: `src/pages/HealthPage.tsx` → `src/features/health/HealthPage.tsx`
- Move: `src/pages/HeatmapPage.tsx` → `src/features/heatmap/HeatmapPage.tsx`
- Move: `src/pages/InsightsPage.tsx` → `src/features/insights/InsightsPage.tsx`
- Move: `src/pages/ApiKeysPage.tsx` → `src/features/api-keys/ApiKeysPage.tsx`
- Move: `src/services/apiKeyApi.ts` → `src/features/api-keys/apiKeyApi.ts`
- Move: `src/pages/SettingsPage.tsx` → `src/features/settings/SettingsPage.tsx`
- Move: `src/services/settingsApi.ts` → `src/features/settings/settingsApi.ts`
- Move: `src/pages/ArchitecturePage.tsx` → `src/features/architecture/ArchitecturePage.tsx`
- Move: `src/pages/PublicPortal.tsx` → `src/features/public/PublicPortal.tsx`

- [ ] **Step 1: Split insightsApi.ts — create healthApi.ts**

Create `src/features/health/healthApi.ts`:

```ts
// src/features/health/healthApi.ts
import { api } from "@/shared/lib/apiClient";

export interface AgencyHealthData {
  agencies: {
    id: string; name: string; shortName: string;
    status: 'healthy' | 'degraded' | 'down';
    uptime: number; currentLatency: number; avgLatency: number;
    errorRate: number; requestsPerMin: number; lastCheckedAt: string;
  }[];
  historical: Array<Record<string, string | number>>;
  incidents: {
    agency: string; type: string; severity: 'info' | 'warning' | 'critical';
    message: string; occurredAt: string; resolvedAt: string;
  }[];
  slaCompliance: { agency: string; uptime: number; target: number; met: boolean }[];
  generatedAt: string;
}

export function fetchAgencyHealth(): Promise<AgencyHealthData> {
  return api.get<AgencyHealthData>('/api/v1/agency-health');
}
```

- [ ] **Step 2: Create heatmapApi.ts**

Create `src/features/heatmap/heatmapApi.ts`:

```ts
// src/features/heatmap/heatmapApi.ts
import { api } from "@/shared/lib/apiClient";

export type HeatmapRange = '7d' | '30d' | '90d';

export interface UsageHeatmapData {
  range: HeatmapRange; days: number; sampleSize: number; totalMessages: number;
  days_labels: string[]; hours: number[];
  agencies: { id: string; name: string }[];
  hourlyByAgency: { agency: string; agencyId: string; data: number[] }[];
  dayHourMatrix: { day: string; dayIndex: number; data: number[] }[];
  insights: {
    peakDay: string; peakHour: string; peakValue: number; totalRequests: number;
    businessHoursPercent: number;
    busiest: { agency: string; total: number; peakHour: number };
    recommendation: string;
  };
  generatedAt: string;
}

export function fetchUsageHeatmap(range: HeatmapRange = '7d'): Promise<UsageHeatmapData> {
  return api.get<UsageHeatmapData>(`/api/v1/usage-heatmap?range=${range}`);
}
```

- [ ] **Step 3: Move remaining page and service files**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

git mv pages/HistoryPage.tsx features/history/HistoryPage.tsx
git mv services/historyApi.ts features/history/historyApi.ts

git mv pages/HealthPage.tsx features/health/HealthPage.tsx
git mv pages/HeatmapPage.tsx features/heatmap/HeatmapPage.tsx
git mv pages/InsightsPage.tsx features/insights/InsightsPage.tsx

git mv pages/ApiKeysPage.tsx features/api-keys/ApiKeysPage.tsx
git mv services/apiKeyApi.ts features/api-keys/apiKeyApi.ts

git mv pages/SettingsPage.tsx features/settings/SettingsPage.tsx
git mv services/settingsApi.ts features/settings/settingsApi.ts

git mv pages/ArchitecturePage.tsx features/architecture/ArchitecturePage.tsx
git mv pages/PublicPortal.tsx features/public/PublicPortal.tsx
```

- [ ] **Step 4: Update imports for moved files**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/services/historyApi'|from '@/features/history/historyApi'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/services/apiKeyApi'|from '@/features/api-keys/apiKeyApi'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/services/settingsApi'|from '@/features/settings/settingsApi'|g"
```

- [ ] **Step 5: Update insightsApi imports in HealthPage and HeatmapPage**

In `src/features/health/HealthPage.tsx`, replace the import line:

```
from '@/services/insightsApi'
```
with:
```
from './healthApi'
```

In `src/features/heatmap/HeatmapPage.tsx`, replace the import line:
```
from '@/services/insightsApi'
```
with:
```
from './heatmapApi'
```

In `src/features/insights/InsightsPage.tsx`, replace the import:
```
from '@/services/insightsApi'
```
with:
```
from '@/services/insightsApi'
```
*(Keep for now — InsightsPage is commented out; leave `services/insightsApi.ts` until cleanup in Task 13.)*

Also update `useInsights.ts` imports:

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src
```

In `hooks/useInsights.ts`:
- `useAgencyHealth` should now import from `features/health/healthApi`
- `useUsageHeatmap` should now import from `features/heatmap/heatmapApi`

Move and rewrite the file:

```bash
# split useInsights.ts into feature-specific hooks
```

Create `src/features/health/useHealth.ts`:

```ts
// src/features/health/useHealth.ts
import { useQuery } from '@tanstack/react-query';
import { fetchAgencyHealth } from './healthApi';

export function useAgencyHealth() {
  return useQuery({
    queryKey: ['agency-health'],
    queryFn: fetchAgencyHealth,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });
}
```

Create `src/features/heatmap/useHeatmap.ts`:

```ts
// src/features/heatmap/useHeatmap.ts
import { useQuery } from '@tanstack/react-query';
import { fetchUsageHeatmap } from './heatmapApi';
import type { HeatmapRange } from './heatmapApi';

export function useUsageHeatmap(range: HeatmapRange = '7d') {
  return useQuery({
    queryKey: ['usage-heatmap', range],
    queryFn: () => fetchUsageHeatmap(range),
    staleTime: 60_000,
  });
}
```

Create `src/features/insights/useInsights.ts` (for the disabled InsightsPage):

```ts
// src/features/insights/useInsights.ts
import { useQuery } from '@tanstack/react-query';
import { fetchAnalyticsInsights } from '@/services/insightsApi';

export function useAnalyticsInsights() {
  return useQuery({
    queryKey: ['analytics-insights'],
    queryFn: fetchAnalyticsInsights,
    staleTime: 5 * 60_000,
  });
}
```

- [ ] **Step 6: Update HealthPage to import from new hook**

In `src/features/health/HealthPage.tsx`:
- Replace `from '@/hooks/useInsights'` with `from './useHealth'`
- Keep only the `useAgencyHealth` import

In `src/features/heatmap/HeatmapPage.tsx`:
- Replace `from '@/hooks/useInsights'` with `from './useHeatmap'`
- Keep only the `useUsageHeatmap` import

In `src/features/insights/InsightsPage.tsx`:
- Replace `from '@/hooks/useInsights'` with `from './useInsights'`

Delete the old split hooks file:
```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src
git rm hooks/useInsights.ts
```

- [ ] **Step 7: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "refactor: move remaining features (history, health, heatmap, api-keys, settings, architecture, public)"
```

---

## Task 11: Update App.tsx + layout imports

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/shared/components/layout/AppSidebar.tsx`

- [ ] **Step 1: Rewrite App.tsx with updated imports**

Replace the full contents of `src/App.tsx`:

```tsx
// src/App.tsx
import { Toaster } from "@/shared/components/ui/toaster";
import { Toaster as Sonner } from "@/shared/components/ui/sonner";
import { TooltipProvider } from "@/shared/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/shared/components/ThemeProvider";
import { AuthProvider } from "@/features/auth/useAuth";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { AppLayout } from "@/shared/components/layout/AppLayout";
import ChatPage from "@/features/chat/ChatPage";
import DashboardPage from "@/features/dashboard/DashboardPage";
import ExecutivePage from "@/features/executive/ExecutivePage";
// import InsightsPage from "@/features/insights/InsightsPage";
import HealthPage from "@/features/health/HealthPage";
import HeatmapPage from "@/features/heatmap/HeatmapPage";
import AgenciesPage from "@/features/agencies/AgenciesPage";
import AgencyDetailPage from "@/features/agencies/AgencyDetailPage";
import HistoryPage from "@/features/history/HistoryPage";
import ArchitecturePage from "@/features/architecture/ArchitecturePage";
import ConnectionLogsPage from "@/features/connection-logs/ConnectionLogsPage";
import PublicPortal from "@/features/public/PublicPortal";
import LoginPage from "@/features/auth/LoginPage";
import SignupPage from "@/features/auth/SignupPage";
import ForgotPasswordPage from "@/features/auth/ForgotPasswordPage";
import ResetPasswordPage from "@/features/auth/ResetPasswordPage";
import ApiKeysPage from "@/features/api-keys/ApiKeysPage";
import SettingsPage from "@/features/settings/SettingsPage";
import NotFound from "@/pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
      <AuthProvider>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<PublicPortal />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />

              <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/executive" element={<ExecutivePage />} />
                {/* <Route path="/insights" element={<InsightsPage />} /> */}
                <Route path="/health" element={<HealthPage />} />
                <Route path="/heatmap" element={<HeatmapPage />} />
                <Route path="/agencies" element={<AgenciesPage />} />
                <Route path="/agencies/:id" element={<AgencyDetailPage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="/connection-logs" element={<ConnectionLogsPage />} />
                <Route path="/architecture" element={<ArchitecturePage />} />
                <Route path="/api-keys" element={<ApiKeysPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>

              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      </AuthProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
```

Note: `NotFound` and `Index` remain at `src/pages/` since they're tiny utility pages.

- [ ] **Step 2: Update AppSidebar.tsx imports**

In `src/shared/components/layout/AppSidebar.tsx`, update the two feature imports:

```ts
// Change:
import { useAgencies } from "@/hooks/useAgencies";
import { useAuth } from "@/hooks/useAuth";

// To:
import { useAgencies } from "@/features/agencies/useAgencies";
import { useAuth } from "@/features/auth/useAuth";
```

- [ ] **Step 3: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "refactor: update App.tsx and AppSidebar with feature import paths"
```

---

## Task 12: Clean up empty old directories

- [ ] **Step 1: Remove now-empty source directories**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

# Remove empty dirs (will fail gracefully if non-empty, which would indicate missed files)
rmdir hooks 2>/dev/null && echo "hooks/ removed" || echo "hooks/ not empty — check remaining files"
rmdir services 2>/dev/null && echo "services/ removed" || echo "services/ not empty — check remaining files"
rmdir pages 2>/dev/null && echo "pages/ not empty (NotFound.tsx, Index.tsx remain)" || true
rmdir components/agencies 2>/dev/null || true
rmdir components/auth 2>/dev/null || true
rmdir components/chat 2>/dev/null || true
rmdir components/dashboard 2>/dev/null || true
rmdir components/layout 2>/dev/null || true
rmdir components 2>/dev/null || echo "components/ not empty — check remaining files"
rmdir lib 2>/dev/null && echo "lib/ removed" || echo "lib/ not empty"
rmdir data 2>/dev/null && echo "data/ removed" || echo "data/ not empty"
rmdir types 2>/dev/null && echo "types/ removed" || echo "types/ not empty"
```

- [ ] **Step 2: Move utils/ to shared and update imports**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

git mv utils/exportExecutiveReport.ts features/executive/exportExecutiveReport.ts
git mv utils/exportHistory.ts features/history/exportHistory.ts
rmdir utils 2>/dev/null && echo "utils/ removed" || echo "utils/ not empty"
```

Update any imports of `@/utils/exportExecutiveReport` → `@/features/executive/exportExecutiveReport` and `@/utils/exportHistory` → `@/features/history/exportHistory`:

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/utils/exportExecutiveReport'|from '@/features/executive/exportExecutiveReport'|g"
find . -name "*.ts" -o -name "*.tsx" | xargs sed -i "s|from '@/utils/exportHistory'|from '@/features/history/exportHistory'|g"
```

`src/pages/NotFound.tsx` and `src/pages/Index.tsx` remain in `src/pages/` — they are tiny utility pages not covered by the feature migration.

- [ ] **Step 3: Delete the now-unused services/insightsApi.ts if present**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src
git rm services/insightsApi.ts 2>/dev/null || echo "already removed"
```

- [ ] **Step 4: Commit cleanup**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "chore: remove empty legacy directories after feature migration"
```

---

## Task 13: TypeScript check + full test run

- [ ] **Step 1: Run TypeScript check — expect zero errors**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend
pnpm exec tsc --noEmit --project tsconfig.app.json
```

Expected: exits with code 0, no output.

If there are errors: fix each one by updating the import path in the reported file to point to the new `@/features/...` or `@/shared/...` location.

- [ ] **Step 2: Run the test suite**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend
pnpm test
```

Expected: all tests pass.

- [ ] **Step 3: Run the linter**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend
pnpm lint
```

Fix any import-related lint errors.

- [ ] **Step 4: Commit any fixes**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git add -A
git commit -m "fix: resolve TypeScript and lint errors after feature migration"
```

---

## Task 14: Final verification + merge

- [ ] **Step 1: Verify directory structure is clean**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

# Confirm no stray files remain in old locations
ls hooks/ 2>/dev/null && echo "ERROR: hooks/ still has files" || echo "hooks/ clean"
ls services/ 2>/dev/null && echo "ERROR: services/ still has files" || echo "services/ clean"
ls lib/ 2>/dev/null && echo "ERROR: lib/ still has files" || echo "lib/ clean"
ls types/ 2>/dev/null && echo "ERROR: types/ still has files" || echo "types/ clean"
ls data/ 2>/dev/null && echo "ERROR: data/ still has files" || echo "data/ clean"
```

- [ ] **Step 2: Confirm no old-path imports remain**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src

# Should return empty (no remaining old-path imports)
grep -r "from '@/hooks/" . --include="*.ts" --include="*.tsx" | grep -v "node_modules"
grep -r "from '@/services/" . --include="*.ts" --include="*.tsx" | grep -v "node_modules"
grep -r "from '@/pages/" . --include="*.ts" --include="*.tsx" | grep -v "node_modules"
grep -r "from '@/components/agencies" . --include="*.ts" --include="*.tsx"
grep -r "from '@/components/auth" . --include="*.ts" --include="*.tsx"
grep -r "from '@/components/chat" . --include="*.ts" --include="*.tsx"
grep -r "from '@/components/dashboard" . --include="*.ts" --include="*.tsx"
grep -r "from '@/components/layout" . --include="*.ts" --include="*.tsx"
```

Expected: all return empty.

- [ ] **Step 3: Final build check**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend
pnpm build 2>&1 | tail -20
```

Expected: `✓ built in ...` with no errors.

- [ ] **Step 4: Open a PR**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
git push -u origin refactor/frontend-feature-structure
gh pr create \
  --title "refactor: migrate frontend to feature-based structure" \
  --body "$(cat <<'EOF'
## Summary
- Migrated all frontend code from layer-based (`pages/`, `hooks/`, `services/`, `components/`) to feature-based structure (`src/features/<feature>/`)
- Shared infrastructure (UI components, layout, lib, hooks, types) moved to `src/shared/`
- Decomposed 4 large page files: AgencyDetailPage (439→~60 lines), ExecutivePage (368→~55 lines), DashboardPage (317→~70 lines), ConnectionLogsPage (348→~55 lines)
- No logic changes — pure reorganization

## Test plan
- [ ] TypeScript compiles with zero errors
- [ ] `pnpm test` passes
- [ ] All routes accessible in browser
- [ ] Agency detail page loads with tabs working
- [ ] Dashboard charts render
- [ ] Connection logs table + filters work
EOF
)"
```
