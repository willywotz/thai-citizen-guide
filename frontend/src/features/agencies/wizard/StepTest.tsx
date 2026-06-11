import { Wifi } from "lucide-react";

import { Button } from "@/shared/components/ui/button";

import { ConnectionTestResult } from "../ConnectionTestResult";
import { useTestConnection } from "../useAgencies";

interface Props {
  agencyId: string;
}

export function StepTest({ agencyId }: Props) {
  const testMutation = useTestConnection();

  return (
    <div className="space-y-4 max-w-lg">
      <p className="text-sm text-muted-foreground">
        ทดสอบการเชื่อมต่อกับ endpoint ที่ตั้งค่าไว้ — หากไม่สำเร็จยังสามารถบันทึกเป็น Draft แล้วกลับมาแก้ไขภายหลังได้
      </p>
      <Button onClick={() => testMutation.mutate({ agencyId })} disabled={testMutation.isPending}>
        <Wifi className="h-4 w-4 mr-1.5" />
        {testMutation.isPending ? "กำลังทดสอบ…" : "ทดสอบการเชื่อมต่อ"}
      </Button>
      {(testMutation.isPending || testMutation.data || testMutation.isError) && (
        <ConnectionTestResult
          result={
            testMutation.data ??
            (testMutation.isError
              ? { success: false, error: `ทดสอบไม่สำเร็จ: ${testMutation.error?.message ?? "Request failed"}` }
              : null)
          }
          loading={testMutation.isPending}
        />
      )}
    </div>
  );
}
