import { useState, useMemo } from "react";
import { Input } from "@/shared/components/ui/input";
import { Button } from "@/shared/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import {
  Search,
  CheckCircle2,
  XCircle,
  Loader2,
  X,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Activity,
} from "lucide-react";
import { useConnectionLogs } from "@/hooks/useConnectionLogs";
import type { ConnectionLog } from "@/shared/types/connectionLog";
import { useAgencies } from "@/features/agencies/useAgencies";
import { format } from "date-fns";
import { cn } from "@/shared/lib/utils";
import { useQueryClient } from "@tanstack/react-query";
import { useConnectionLogInfo } from "@/hooks/useConnectionLogs";

const PAGE_SIZE = 20;

const connectionTypeColors: Record<string, string> = {
  MCP: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  API: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  A2A: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

export default function ConnectionLogsPage() {
  const queryClient = useQueryClient();
  const { data: agencies = [] } = useAgencies();

  // Server-side: search + page
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data: logInfo } = useConnectionLogInfo();

  // Client-side filters on current page items
  const [filterStatus, setFilterStatus] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string | null>(null);
  const [filterAgency, setFilterAgency] = useState<string | null>(null);
  const [selectedLog, setSelectedLog] = useState<ConnectionLog | null>(null);

  const { data, isLoading, isFetching } = useConnectionLogs({ page, limit: PAGE_SIZE, search });

  const items = data?.items ?? [];
  const totalItems = data?.total_items ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));

  const agencyMap = useMemo(
    () => Object.fromEntries(agencies.map((a) => [a.id, a.shortName])),
    [agencies]
  );

  const filtered = useMemo(() => {
    return items.filter((log) => {
      if (filterStatus && log.status !== filterStatus) return false;
      if (filterType && log.connection_type !== filterType) return false;
      if (filterAgency && log.agency_id !== filterAgency) return false;
      return true;
    });
  }, [items, filterStatus, filterType, filterAgency]);

  const stats = useMemo(() => {
    const success = items.filter((l) => l.status === "success").length;
    const error = items.filter((l) => l.status === "error").length;
    const avgLatency = items.length
      ? Math.round(items.reduce((s, l) => s + l.latency_ms, 0) / items.length)
      : 0;
    return { total: totalItems, success, error, avgLatency };
  }, [items, totalItems]);

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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold text-foreground">ประวัติการเชื่อมต่อ</h2>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => queryClient.invalidateQueries({ queryKey: ["connection-logs"] })}
          disabled={isFetching}
        >
          <RefreshCw className={cn("h-3.5 w-3.5 mr-1", isFetching && "animate-spin")} />
          รีเฟรช
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "ทั้งหมด", value: logInfo?.total_connections ?? 0, color: "text-foreground" },
          { label: "สำเร็จ", value: logInfo?.successful_connections ?? 0, color: "text-green-600 dark:text-green-400" },
          { label: "ล้มเหลว", value: logInfo?.failed_connections ?? 0, color: "text-destructive" },
          { label: "Latency เฉลี่ย (24 ชม.)", value: `${logInfo?.average_latency_ms ?? 0} ms`, color: "text-foreground" },
        ].map((s) => (
          <div key={s.label} className="border rounded-lg p-3 bg-card">
            <p className="text-xs text-muted-foreground">{s.label}</p>
            <p className={`text-xl font-semibold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="ค้นหา detail..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="pl-9 h-8 text-sm"
          />
        </div>

        <div className="flex gap-1">
          {([null, "success", "error"] as const).map((s) => (
            <button
              key={s ?? "all"}
              onClick={() => setFilterStatus(s)}
              className={cn(
                "text-xs px-3 py-1.5 rounded-full border transition-colors",
                filterStatus === s
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:bg-accent"
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
              onClick={() => setFilterType(filterType === t ? null : t)}
              className={cn(
                "text-xs px-3 py-1.5 rounded-full border transition-colors",
                filterType === t
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:bg-accent"
              )}
            >
              {t}
            </button>
          ))}
        </div>

        {agencies.length > 0 && (
          <select
            value={filterAgency ?? ""}
            onChange={(e) => setFilterAgency(e.target.value || null)}
            className="text-xs h-8 px-2 rounded-md border border-border bg-background text-foreground"
          >
            <option value="">หน่วยงานทั้งหมด</option>
            {agencies.map((a) => (
              <option key={a.id} value={a.id}>{a.shortName}</option>
            ))}
          </select>
        )}

        {hasFilters && (
          <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground" onClick={resetFilters}>
            <X className="h-3.5 w-3.5 mr-1" />
            ล้างตัวกรอง
          </Button>
        )}
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
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
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-10 text-sm">
                    ไม่พบข้อมูล
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((log) => (
                  <TableRow key={log.id} className="cursor-pointer hover:bg-accent/50" onClick={() => setSelectedLog(log)}>
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
                        <span className="flex items-center gap-1 text-green-600 dark:text-green-400 text-xs">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          สำเร็จ
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-destructive text-xs">
                          <XCircle className="h-3.5 w-3.5" />
                          ล้มเหลว
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-right tabular-nums whitespace-nowrap">
                      <span className={cn(log.latency_ms > 1000 ? "text-amber-600" : "text-muted-foreground")}>
                        {log.latency_ms} ms
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate whitespace-nowrap" title={log.detail}>
                      {log.detail || "—"}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs text-muted-foreground">
            หน้า {page}/{totalPages} · {totalItems} รายการ
          </span>
          <div className="flex items-center gap-1">
            <Button variant="outline" size="icon" className="h-7 w-7" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              const p = totalPages <= 7 ? i + 1 : page <= 4 ? i + 1 : page >= totalPages - 3 ? totalPages - 6 + i : page - 3 + i;
              return (
                <Button key={p} variant={p === page ? "default" : "outline"} size="icon" className="h-7 w-7 text-xs" onClick={() => setPage(p)}>
                  {p}
                </Button>
              );
            })}
            <Button variant="outline" size="icon" className="h-7 w-7" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
      {/* Detail Dialog */}
      <Dialog open={!!selectedLog} onOpenChange={(o) => { if (!o) setSelectedLog(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm">
              {selectedLog?.status === "success" ? (
                <CheckCircle2 className="h-4 w-4 text-green-600" />
              ) : (
                <XCircle className="h-4 w-4 text-destructive" />
              )}
              Connection Log Detail
            </DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-muted-foreground">วันที่/เวลา</p>
                  <p className="font-medium text-xs">{format(selectedLog.created_at, "dd/MM/yyyy HH:mm:ss")}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">หน่วยงาน</p>
                  <p className="font-medium text-xs">{agencyMap[selectedLog.agency_id] || selectedLog.agency_id || "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">ประเภทการเชื่อมต่อ</p>
                  <span className={cn("text-[10px] px-2 py-0.5 rounded-full font-medium", connectionTypeColors[selectedLog.connection_type] || "bg-muted text-muted-foreground")}>
                    {selectedLog.connection_type}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Action</p>
                  <p className="font-medium text-xs capitalize">{selectedLog.action}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">สถานะ</p>
                  {selectedLog.status === "success" ? (
                    <span className="flex items-center gap-1 text-green-600 dark:text-green-400 text-xs font-medium">
                      <CheckCircle2 className="h-3.5 w-3.5" /> สำเร็จ
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-destructive text-xs font-medium">
                      <XCircle className="h-3.5 w-3.5" /> ล้มเหลว
                    </span>
                  )}
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Latency</p>
                  <p className={cn("font-medium text-xs", selectedLog.latency_ms > 15_000 ? "text-amber-600" : "")}>
                    {selectedLog.latency_ms} ms
                  </p>
                </div>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">รายละเอียด</p>
                <pre className="text-xs bg-muted rounded-md p-3 whitespace-pre-wrap break-all font-mono leading-relaxed max-h-48 overflow-y-auto">
                  {selectedLog.detail || "—"}
                </pre>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
