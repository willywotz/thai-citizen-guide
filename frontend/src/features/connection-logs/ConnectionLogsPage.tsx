import { useState, useMemo, useCallback } from "react";
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
import { PAGE_SIZE as PAGE_SIZES } from "@/shared/constants/query";
import { usePaginatedFilter } from "@/shared/hooks/usePaginatedFilter";

const PAGE_SIZE = PAGE_SIZES.connectionLogs;

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
  const { data, isLoading, isFetching, isError, refetch } = useConnectionLogs({ page, limit: PAGE_SIZE, search });

  const items = data?.items ?? [];
  const totalItems = data?.total_items ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));

  const agencyMap = useMemo(
    () => Object.fromEntries(agencies.map((a) => [a.id, a.shortName])),
    [agencies]
  );

  const logFilterFn = useCallback(
    (log: ConnectionLog) => {
      if (filterStatus && log.status !== filterStatus) return false;
      if (filterType && log.connection_type !== filterType) return false;
      if (filterAgency && log.agency_id !== filterAgency) return false;
      return true;
    },
    [filterStatus, filterType, filterAgency],
  );

  const { filteredItems: filtered } = usePaginatedFilter({
    items,
    pageSize: PAGE_SIZE,
    filterFn: logFilterFn,
  });

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
        items={filtered} isLoading={isLoading} isError={isError} onRetry={() => void refetch()} agencyMap={agencyMap}
        selectedLog={selectedLog} onSelectLog={setSelectedLog} onCloseLog={() => setSelectedLog(null)}
        page={page} totalPages={totalPages} totalItems={totalItems} onPageChange={setPage}
      />
    </div>
  );
}
