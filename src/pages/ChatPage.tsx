import { useEffect } from 'react';
import { Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { agencies, suggestedQuestions } from '@/data/mockData';
import { useSearchParams } from 'react-router-dom';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { AgentStepDisplay } from '@/components/chat/AgentStepDisplay';
import { useChat } from '@/hooks/useChat';

export default function ChatPage() {
  const {
    messages, input, setInput, isTyping, activeStepCount, currentSteps,
    scrollRef, handleSend, handleRate, hasMessages,
  } = useChat();
  const [searchParams, setSearchParams] = useSearchParams();

  // Handle query from URL
  useEffect(() => {
    const q = searchParams.get('q');
    if (q) {
      setSearchParams({});
      handleSend(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      <ScrollArea className="flex-1 p-4">
        {!hasMessages && !isTyping ? (
          <div className="flex flex-col items-center justify-center h-full min-h-[60vh] text-center px-4">
            <div className="w-16 h-16 rounded-2xl gov-gradient flex items-center justify-center text-white text-2xl font-bold mb-4">AI</div>
            <h2 className="text-xl font-semibold text-foreground mb-2">AI Chatbot Portal กลาง</h2>
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
                  <button key={i} onClick={() => handleSend(q)}
                    className="text-left text-sm bg-card border border-border rounded-xl p-3 hover:bg-accent hover:border-primary/30 transition-colors">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} onRate={handleRate} />
            ))}
            {isTyping && (
              <div className="flex items-start gap-3 mb-4">
                <div className="w-8 h-8 rounded-full gov-gradient flex items-center justify-center text-white text-sm shrink-0">AI</div>
                <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3 max-w-[75%]">
                  {activeStepCount > 0 ? (
                    <AgentStepDisplay steps={currentSteps} visibleCount={activeStepCount} />
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

      <div className="border-t border-border bg-card p-3">
        <div className="max-w-3xl mx-auto flex gap-2">
          <input value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="พิมพ์คำถามของคุณที่นี่..."
            className="flex-1 bg-background border border-input rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
          <Button onClick={() => handleSend()} size="icon" className="rounded-xl shrink-0" disabled={!input.trim() || isTyping}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
