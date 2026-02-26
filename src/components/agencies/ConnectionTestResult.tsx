import { CheckCircle2, Loader2, Circle } from "lucide-react";

interface TestStep {
  step: number;
  label: string;
  status: string;
  time: number;
}

interface TestResult {
  success: boolean;
  protocol: string;
  version: string;
  steps: TestStep[];
  latency: string;
  capabilities?: string[];
  agentCard?: { name: string; skills: string[] };
  endpoints?: string[];
}

interface Props {
  result: TestResult | null;
  loading: boolean;
}

export function ConnectionTestResult({ result, loading }: Props) {
  if (!loading && !result) return null;

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-4 space-y-3 text-sm">
      <div className="flex items-center gap-2 font-medium text-foreground">
        {loading ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : <CheckCircle2 className="h-4 w-4 text-green-500" />}
        {loading ? "กำลังทดสอบการเชื่อมต่อ..." : `เชื่อมต่อสำเร็จ — ${result?.protocol} ${result?.version}`}
      </div>

      <div className="space-y-1.5 pl-6">
        {(result?.steps || []).map((s, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            {loading && i === (result?.steps?.length ?? 0) - 1
              ? <Loader2 className="h-3 w-3 animate-spin text-primary" />
              : s.status === 'done'
                ? <CheckCircle2 className="h-3 w-3 text-green-500" />
                : <Circle className="h-3 w-3 text-muted-foreground" />}
            <span className="text-foreground">{s.label}</span>
            <span className="ml-auto text-muted-foreground">{s.time}ms</span>
          </div>
        ))}
      </div>

      {result && !loading && (
        <div className="pl-6 text-xs text-muted-foreground space-y-1">
          <p>Latency: <span className="font-medium text-foreground">{result.latency}</span></p>
          {result.capabilities && <p>Capabilities: {result.capabilities.join(', ')}</p>}
          {result.agentCard && <p>Agent: {result.agentCard.name} — Skills: {result.agentCard.skills.join(', ')}</p>}
          {result.endpoints && <p>Endpoints: {result.endpoints.join(', ')}</p>}
        </div>
      )}
    </div>
  );
}
