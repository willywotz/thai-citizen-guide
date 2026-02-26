import { Send, Search, ArrowRight, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { agencies, suggestedQuestions } from '@/data/mockData';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { AgentStepDisplay } from '@/components/chat/AgentStepDisplay';
import { LandingHero } from '@/components/public/LandingHero';
import { AgencyCards } from '@/components/public/AgencyCards';
import { SuggestedQuestions } from '@/components/public/SuggestedQuestions';
import { useChat } from '@/hooks/useChat';
import { useState } from 'react';

export default function PublicPortal() {
  const {
    messages, input, setInput, isTyping, activeStepCount, currentSteps,
    scrollRef, handleSend, handleRate, reset, hasMessages,
  } = useChat();
  const [chatMode, setChatMode] = useState(false);

  const onSend = (text?: string) => {
    if (!chatMode) setChatMode(true);
    handleSend(text);
  };

  const handleBack = () => {
    setChatMode(false);
    reset();
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-sm px-6 py-3 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-2.5">
          {chatMode && (
            <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg mr-1" onClick={handleBack}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
          )}
          <div className="w-9 h-9 rounded-xl gov-gradient flex items-center justify-center text-white font-bold text-sm shadow-md">AI</div>
          <span className="font-semibold text-foreground">AI Portal กลาง</span>
        </div>
        <a href="/" className="text-xs text-primary hover:underline flex items-center gap-1 font-medium">
          เข้าสู่ระบบเจ้าหน้าที่ <ArrowRight className="w-3 h-3" />
        </a>
      </header>

      {chatMode ? (
        <>
          <ScrollArea className="flex-1 p-4">
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
          </ScrollArea>

          <div className="border-t border-border bg-card p-3">
            <div className="max-w-3xl mx-auto flex gap-2">
              <input value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && onSend()}
                placeholder="พิมพ์คำถามของคุณที่นี่..."
                className="flex-1 bg-background border border-input rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
              <Button onClick={() => onSend()} size="icon" className="rounded-xl shrink-0" disabled={!input.trim() || isTyping}>
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      ) : (
        <>
          <main className="flex-1 flex flex-col items-center justify-center px-4 py-16">
            <LandingHero />

            {/* Search */}
            <div className="w-full max-w-xl mb-12">
              <p className="text-xs text-muted-foreground mb-2 ml-1">ถามคำถามเกี่ยวกับบริการภาครัฐ</p>
              <div className="relative flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input value={input} onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && onSend()}
                    placeholder="พิมพ์คำถามของคุณ เช่น ขั้นตอนทำบัตรประชาชนใหม่..."
                    className="w-full bg-card border border-input rounded-2xl pl-11 pr-4 py-4 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:border-primary shadow-sm transition-shadow focus:shadow-md" />
                </div>
                <Button onClick={() => onSend()} size="icon" className="rounded-2xl h-[52px] w-[52px] shrink-0 shadow-sm" disabled={!input.trim()}>
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <AgencyCards agencies={agencies} />
            <SuggestedQuestions questions={suggestedQuestions} agencies={agencies} onSelect={onSend} />
          </main>

          <footer className="border-t border-border py-6 px-6">
            <div className="max-w-xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-md gov-gradient flex items-center justify-center text-white font-bold text-[8px]">AI</div>
                <span className="text-xs text-muted-foreground">© 2568 AI Portal กลาง</span>
              </div>
              <div className="flex gap-4 text-xs text-muted-foreground">
                <a href="#" className="hover:text-foreground transition-colors">เกี่ยวกับระบบ</a>
                <a href="#" className="hover:text-foreground transition-colors">นโยบายข้อมูล</a>
                <a href="#" className="hover:text-foreground transition-colors">ติดต่อเรา</a>
              </div>
            </div>
          </footer>
        </>
      )}
    </div>
  );
}
