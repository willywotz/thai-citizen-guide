import { useState } from "react";
import { Bot, User, Brain, ChevronDown, ChevronUp } from "lucide-react";
import { cn, parseThinkContent } from "@/shared/lib/utils";
import type { ConversationMessage } from "@/shared/types";
import ReactMarkdown from "react-markdown";

export function MessageItem({ msg }: { msg: ConversationMessage }) {
  const [thinkOpen, setThinkOpen] = useState(false);
  const { thinking, answer } = parseThinkContent(msg.content);

  return (
    <div className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      {msg.role === 'assistant' && (
        <div className="shrink-0 w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center">
          <Bot className="h-4 w-4 text-primary" />
        </div>
      )}
      
      <div className={`rounded-lg px-3 py-2 max-w-[80%] text-sm ${
        msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'
      }`}>
        {thinking && (
          <div className="mb-2 rounded-lg border border-border bg-muted/40 overflow-hidden">
            <button
              onClick={() => setThinkOpen(!thinkOpen)}
              className="flex w-full items-center gap-1.5 px-3 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <Brain className="h-3.5 w-3.5 shrink-0" />
              <span className="font-medium">Thinking</span>
              {thinkOpen ? <ChevronUp className="ml-auto h-3.5 w-3.5" /> : <ChevronDown className="ml-auto h-3.5 w-3.5" />}
            </button>
            {thinkOpen && (
              <div className="px-3 pb-3 text-xs text-muted-foreground whitespace-pre-wrap border-t border-border pt-2">
                {thinking}
              </div>
            )}
          </div>
        )}
        
        {msg.role === 'assistant' ? (
          <div className="prose prose-sm dark:prose-invert max-w-none [&>p]:my-1 [&>ul]:my-1">
            <ReactMarkdown>{answer}</ReactMarkdown>
          </div>
        ) : (
          <p>{answer}</p>
        )}
      </div>

      {msg.role === 'user' && (
        <div className="shrink-0 w-7 h-7 rounded-full bg-primary flex items-center justify-center">
          <User className="h-4 w-4 text-primary-foreground" />
        </div>
      )}
    </div>
  );
}