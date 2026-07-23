import { Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { SummaryReference } from '@/shared/types/chat';

/**
 * OneChat v5 executive summary with its `[n]` citations, shown above the raw
 * agency sections. Renders nothing when the upstream produced no summary
 * (v4 mode, summary-generation failure, or a smart-fallback answer).
 */
export function SummaryCard({
  summary,
  references = [],
}: {
  summary?: string | null;
  references?: SummaryReference[];
}) {
  if (!summary?.trim()) return null;

  return (
    <div className="mb-3 rounded-xl border border-primary/30 bg-primary/5 px-3 py-2">
      <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-primary">
        <Sparkles className="h-3.5 w-3.5 shrink-0" />
        สรุป
      </div>
      <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary}</ReactMarkdown>
      </div>
      {references.length > 0 && (
        <ul className="mt-2 space-y-0.5 border-t border-primary/20 pt-2 text-[11px] text-muted-foreground">
          {references.map((ref) => (
            <li key={ref.number}>[{ref.number}] {ref.agency_name}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
