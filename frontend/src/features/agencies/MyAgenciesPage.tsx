import { Check, ChevronDown, ChevronRight, Loader2, X } from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import type { ConformanceReport } from "@/features/agencies/agencyApi";
import type { Agency } from "@/shared/types/agency";

import { AgencyCard } from "./AgencyCard";
import type { TestResult } from "./ConnectionTestResult";
import {
  useAgencyLowRated,
  useMyAgencies,
  useRunConformance,
  useTestConnection,
} from "./useAgencies";

function LowRatedSection({ agencyId }: { agencyId: string }) {
  const [open, setOpen] = useState(false);
  const { data = [], isLoading } = useAgencyLowRated(agencyId, open);

  return (
    <div className="rounded-md border border-border">
      <button
        type="button"
        className="flex w-full items-center gap-1.5 p-2 text-xs font-medium text-foreground"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5" />
        )}
        คำตอบที่ถูกให้คะแนนต่ำ
      </button>
      {open && (
        <div className="px-3 pb-3">
          {isLoading ? (
            <p className="text-xs text-muted-foreground">กำลังโหลด...</p>
          ) : data.length === 0 ? (
            <p className="text-xs text-muted-foreground">ไม่มีคำตอบที่ถูกให้คะแนนต่ำ</p>
          ) : (
            <ul className="space-y-2">
              {data.map((row) => (
                <li key={row.id} className="rounded border border-border p-2 text-xs">
                  <p className="text-foreground">{row.content}</p>
                  {row.feedback_text && (
                    <p className="mt-1 text-muted-foreground">“{row.feedback_text}”</p>
                  )}
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {new Date(row.created_at).toLocaleString("th-TH")}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function ConformanceResult({ report }: { report: ConformanceReport }) {
  return (
    <div className="mt-3 rounded-md border border-border p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-foreground">ผลการทดสอบความสอดคล้อง</span>
        <Badge
          className={`text-[10px] ${
            report.passed
              ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
              : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
          }`}
        >
          {report.passed ? "ผ่าน" : "ไม่ผ่าน"}
        </Badge>
      </div>
      <ul className="space-y-1">
        {report.checks.map((check) => (
          <li key={check.name} className="flex items-start gap-2 text-xs">
            {check.passed ? (
              <Check className="h-3.5 w-3.5 shrink-0 text-green-600 mt-0.5" />
            ) : (
              <X className="h-3.5 w-3.5 shrink-0 text-red-600 mt-0.5" />
            )}
            <span className="text-foreground">{check.name}</span>
            <span className="text-muted-foreground">— {check.detail}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function MyAgenciesPage() {
  const { data: agencies = [], isLoading, isError } = useMyAgencies();
  const testMutation = useTestConnection();
  const conformanceMutation = useRunConformance();

  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult | null>>({});
  const [runningId, setRunningId] = useState<string | null>(null);
  const [reports, setReports] = useState<Record<string, ConformanceReport>>({});

  const handleTest = useCallback(async (agency: Agency) => {
    setTestingId(agency.id);
    setTestResults((prev) => ({ ...prev, [agency.id]: null }));
    try {
      const result = await testMutation.mutateAsync({ agencyId: agency.id });
      setTestResults((prev) => ({ ...prev, [agency.id]: result }));
    } catch (err: unknown) {
      setTestResults((prev) => ({
        ...prev,
        [agency.id]: { success: false, error: err instanceof Error ? err.message : "Connection failed" },
      }));
    } finally {
      setTestingId(null);
    }
  }, [testMutation]);

  const handleRunConformance = async (agency: Agency) => {
    setRunningId(agency.id);
    try {
      const report = await conformanceMutation.mutateAsync(agency.id);
      setReports((prev) => ({ ...prev, [agency.id]: report }));
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "เกิดข้อผิดพลาด");
    } finally {
      setRunningId(null);
    }
  };

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground">หน่วยงานของฉัน</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          จัดการและทดสอบความสอดคล้องของหน่วยงานที่คุณเป็นเจ้าของ
        </p>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">กำลังโหลด...</div>
      ) : isError ? (
        <div className="text-center py-12 text-muted-foreground">เกิดข้อผิดพลาดในการโหลดข้อมูล</div>
      ) : agencies.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">คุณยังไม่มีหน่วยงาน</div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {agencies.map((agency) => {
            const report = reports[agency.id];
            const running = runningId === agency.id;
            const readyToSubmit = agency.status === "draft" && report?.passed === true;
            return (
              <div key={agency.id} className="space-y-2">
                <AgencyCard
                  agency={agency}
                  onTest={handleTest}
                  manageActions={false}
                  testing={testingId === agency.id}
                  testResult={testResults[agency.id] ?? null}
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full"
                  disabled={running}
                  onClick={() => handleRunConformance(agency)}
                >
                  {running && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                  ทดสอบความสอดคล้อง
                </Button>
                {report && <ConformanceResult report={report} />}
                {readyToSubmit && (
                  <p className="text-xs text-green-600">พร้อมส่งเพื่อขออนุมัติ</p>
                )}
                <LowRatedSection agencyId={agency.id} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
