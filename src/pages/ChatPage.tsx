import { useState, useRef, useEffect } from "react";
import { Send, ThumbsUp, ThumbsDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { agencies, suggestedQuestions, mockAgentSteps, mockConversation, type ChatMessage, type AgentStep } from "@/data/mockData";
import { cn } from "@/lib/utils";
import { useSearchParams } from "react-router-dom";

function AgentStepDisplay({ steps, visibleCount }: { steps: AgentStep[]; visibleCount: number }) {
  return (
    <div className="bg-muted/50 rounded-lg p-3 mb-3 space-y-1.5">
      <p className="text-xs font-medium text-muted-foreground mb-2">กระบวนการทำงานของ AI Agent:</p>
      {steps.slice(0, visibleCount).map((step, i) => {
        const isActive = i === visibleCount - 1 && visibleCount <= steps.length;
        const isDone = i < visibleCount - 1 || visibleCount > steps.length;
        return (
          <div key={i} className="flex items-center gap-2 text-xs animate-fade-in">
            <span>{step.icon}</span>
            <span className={cn(
              isDone && 'text-foreground',
              isActive && 'text-primary font-medium',
            )}>
              {step.label}
            </span>
            {isDone && <span className="text-green-600 text-[10px]">✓</span>}
            {isActive && <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />}
          </div>
        );
      })}
    </div>
  );
}

function MessageBubble({ message, onRate }: { message: ChatMessage; onRate?: (id: string, rating: 'up' | 'down') => void }) {
  const isUser = message.role === 'user';
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
          <div className="whitespace-pre-wrap">{message.content}</div>
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
        {/* Rating */}
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
                <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full" onClick={() => onRate(message.id, 'down')}>
                  <ThumbsDown className="h-3.5 w-3.5" />
                </Button>
              </>
            )}
          </div>
        )}
        <p className="text-[10px] text-muted-foreground">{message.timestamp}</p>
      </div>
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [activeStepCount, setActiveStepCount] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const hasMessages = messages.length > 0;
  const [searchParams, setSearchParams] = useSearchParams();

  // Handle query from public portal
  useEffect(() => {
    const q = searchParams.get("q");
    if (q) {
      setSearchParams({});
      handleSend(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeStepCount]);

  const handleRate = (id: string, rating: 'up' | 'down') => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, rating } : m));
  };

  const handleSend = (text?: string) => {
    const question = text || input.trim();
    if (!question) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
      timestamp: new Date().toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);
    setActiveStepCount(0);

    // Animate steps one by one
    const steps = mockAgentSteps;
    steps.forEach((_, i) => {
      setTimeout(() => setActiveStepCount(i + 1), (i + 1) * 600);
    });

    // After all steps, show answer
    setTimeout(() => {
      const aiMsg: ChatMessage = {
        ...mockConversation[1],
        id: (Date.now() + 1).toString(),
        timestamp: new Date().toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }),
        rating: null,
      };
      setMessages(prev => [...prev, aiMsg]);
      setIsTyping(false);
      setActiveStepCount(0);
    }, (steps.length + 1) * 600);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      <ScrollArea className="flex-1 p-4">
        {!hasMessages && !isTyping ? (
          /* Welcome screen */
          <div className="flex flex-col items-center justify-center h-full min-h-[60vh] text-center px-4">
            <div className="w-16 h-16 rounded-2xl gov-gradient flex items-center justify-center text-white text-2xl font-bold mb-4">
              AI
            </div>
            <h2 className="text-xl font-semibold text-foreground mb-2">
              AI Chatbot Portal กลาง
            </h2>
            <p className="text-sm text-muted-foreground mb-6 max-w-md">
              ระบบบูรณาการข้อมูลหน่วยงานภาครัฐ สอบถามข้อมูลจาก 4 หน่วยงานได้ในที่เดียว
            </p>
            <div className="flex flex-wrap justify-center gap-3 mb-8">
              {agencies.map((a) => (
                <div key={a.id} className="flex flex-col items-center gap-1 bg-card border border-border rounded-xl p-3 w-28">
                  <span className="text-2xl">{a.logo}</span>
                  <span className="text-[10px] text-muted-foreground text-center leading-tight">{a.shortName}</span>
                </div>
              ))}
            </div>
            <div className="w-full max-w-lg space-y-2">
              <p className="text-xs text-muted-foreground mb-2">ลองถามคำถามเหล่านี้:</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {suggestedQuestions.map((q, i) => (
                  <button key={i}
                    onClick={() => handleSend(q)}
                    className="text-left text-sm bg-card border border-border rounded-xl p-3 hover:bg-accent hover:border-primary/30 transition-colors">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* Chat messages */
          <div className="max-w-3xl mx-auto">
            {messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} onRate={handleRate} />
            ))}
            {isTyping && (
              <div className="flex items-start gap-3 mb-4">
                <div className="w-8 h-8 rounded-full gov-gradient flex items-center justify-center text-white text-sm shrink-0">AI</div>
                <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3 max-w-[75%]">
                  {activeStepCount > 0 ? (
                    <AgentStepDisplay steps={mockAgentSteps} visibleCount={activeStepCount} />
                  ) : (
                    <div className="flex items-center gap-1">
                      <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  )}
                </div>
              </div>
            )}
            <div ref={scrollRef} />
          </div>
        )}
      </ScrollArea>

      {/* Input area */}
      <div className="border-t border-border bg-card p-3">
        <div className="max-w-3xl mx-auto flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="พิมพ์คำถามของคุณที่นี่..."
            className="flex-1 bg-background border border-input rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <Button onClick={() => handleSend()} size="icon" className="rounded-xl shrink-0"
            disabled={!input.trim() || isTyping}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
