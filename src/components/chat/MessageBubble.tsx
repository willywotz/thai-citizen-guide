import { useState } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/data/mockData";
import { AgentStepDisplay } from "./AgentStepDisplay";
import { FeedbackDialog } from "./FeedbackDialog";
import ReactMarkdown from "react-markdown";

export function MessageBubble({ message, onRate }: { message: ChatMessage; onRate?: (id: string, rating: 'up' | 'down', feedbackText?: string) => void }) {
  const [showFeedback, setShowFeedback] = useState(false);
  const isUser = message.role === 'user';

  const handleThumbsDown = () => {
    setShowFeedback(true);
  };

  const handleFeedbackSubmit = (text: string) => {
    onRate?.(message.id, 'down', text || undefined);
  };

  return (
    <div className={cn("flex gap-3 mb-4", isUser && "flex-row-reverse")}>
      <div className={cn(
        "w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm",
        isUser ? "bg-primary text-primary-foreground" : "gov-gradient text-white"
      )}>
        {isUser ? '👤' : 'AI'}
      </div>
      <div className={cn("max-w-[75%] space-y-2", isUser && "text-right")}>
        <div className={cn(
          "rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground rounded-tr-sm"
            : "bg-card border border-border rounded-tl-sm"
        )}>
          {!isUser && message.agentSteps && <AgentStepDisplay steps={message.agentSteps} visibleCount={message.agentSteps.length + 1} />}
          {isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-table:my-2 prose-hr:my-3">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>
        {!isUser && message.sources && (
          <div className="flex flex-wrap gap-1.5">
            {message.sources.map((src, i) => (
              <a key={i} href={src.url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[10px] bg-accent text-accent-foreground px-2 py-1 rounded-full hover:bg-accent/80 transition-colors">
                📎 {src.agency}: {src.title}
              </a>
            ))}
          </div>
        )}
        {!isUser && onRate && (
          <div className="flex items-center gap-1">
            {message.rating ? (
              <span className="text-xs text-muted-foreground">
                {message.rating === 'up' ? '👍 ขอบคุณสำหรับ feedback!' : '👎 ขอบคุณ จะปรับปรุงต่อไป'}
              </span>
            ) : (
              <>
                <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full" onClick={() => onRate(message.id, 'up')}>
                  <ThumbsUp className="h-3.5 w-3.5" />
                </Button>
                <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full" onClick={handleThumbsDown}>
                  <ThumbsDown className="h-3.5 w-3.5" />
                </Button>
              </>
            )}
          </div>
        )}
        <p className="text-[10px] text-muted-foreground">{message.timestamp}</p>
      </div>

      <FeedbackDialog
        open={showFeedback}
        onClose={() => setShowFeedback(false)}
        onSubmit={handleFeedbackSubmit}
      />
    </div>
  );
}
