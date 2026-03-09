import { CheckCircle2, Loader2, Circle, XCircle, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface TestStep {
  step: number;
  label: string;
  status: string;
  time: number;
}

export interface TestResult {
  success: boolean;
  protocol: string;
  version: string;
  steps: TestStep[];
  latency: string;
  capabilities?: string[];
  agentCard?: { name: string; skills: string[] };
  endpoints?: string[];
  statusCode?: number | null;
  statusText?: string;
  server?: string;
  contentType?: string;
  error?: string;
}

interface Props {
  result: TestResult | null;
  loading: boolean;
}

function StatusCodeBadge({ code }: { code: number }) {
  const variant = code >= 200 && code < 300 ? "default" : code < 400 ? "secondary" : "destructive";
  return (
    <Badge variant={variant} className="text-[10px] font-mono ml-2">
      HTTP {code}
    </Badge>
  );
}

export function ConnectionTestResult({ result, loading }: Props) {
  if (!loading && !result) return null;

  const icon = loading
    ? <Loader2 className="h-4 w-4 animate-spin text-primary" />
    : result?.success
      ? <CheckCircle2 className="h-4 w-4 text-green-500" />
      : <XCircle className="h-4 w-4 text-destructive" />;

  const title = loading
    ? "กำลังทดสอบการเชื่อมต่อ..."
    : result?.success
      ? `เชื่อมต่อสำเร็จ — ${result?.protocol} ${result?.version}`
      : `เชื่อมต่อล้มเหลว — ${result?.error || 'Unknown error'}`;

  return (
    <div className={`rounded-lg border p-4 space-y-3 text-sm ${
      !loading && result && !result.success
        ? "border-destructive/30 bg-destructive/5"
        : "border-border bg-muted/30"
    }`}>
      <div className="flex items-center gap-2 font-medium text-foreground">
        {icon}
        <span className="flex-1">{title}</span>
        {result?.statusCode && <StatusCodeBadge code={result.statusCode} />}
      </div>

      <div className="space-y-1.5 pl-6">
        {(result?.steps || []).map((s, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            {loading && i === (result?.steps?.length ?? 0) - 1
              ? <Loader2 className="h-3 w-3 animate-spin text-primary" />
              : s.status === 'done'
                ? <CheckCircle2 className="h-3 w-3 text-green-500" />
                : s.status === 'error'
                  ? <AlertTriangle className="h-3 w-3 text-destructive" />
                  : <Circle className="h-3 w-3 text-muted-foreground" />}
            <span className="text-foreground">{s.label}</span>
            <span className="ml-auto text-muted-foreground">{s.time}ms</span>
          </div>
        ))}
      </div>

      {result && !loading && (
        <div className="pl-6 text-xs text-muted-foreground space-y-1">
          <p>Latency: <span className="font-medium text-foreground">{result.latency}</span></p>
          {result.statusCode && (
            <p>Status: <span className="font-medium text-foreground">{result.statusCode} {result.statusText}</span></p>
          )}
          {result.server && result.server !== 'unknown' && (
            <p>Server: <span className="font-medium text-foreground">{result.server}</span></p>
          )}
          {result.contentType && result.contentType !== 'unknown' && (
            <p>Content-Type: <span className="font-medium text-foreground">{result.contentType}</span></p>
          )}
          {result.capabilities && <p>Capabilities: {result.capabilities.join(', ')}</p>}
          {result.agentCard && <p>Agent: {result.agentCard.name} — Skills: {result.agentCard.skills.join(', ')}</p>}
          {result.endpoints && <p>Endpoints: {result.endpoints.join(', ')}</p>}
        </div>
      )}
    </div>
  );
}
