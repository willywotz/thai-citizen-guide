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
