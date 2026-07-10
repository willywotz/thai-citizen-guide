import { Send, Search, X, ArrowRight, ArrowLeft, Bot } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { MessageBubble } from '@/features/chat/MessageBubble';
import { AgentStepDisplay, StreamingProgress } from '@/features/chat/AgentStepDisplay';
import { LandingHero } from '@/features/public/LandingHero';
import { SuggestedQuestions } from '@/features/public/SuggestedQuestions';
import { AgencyCards } from '@/features/public/AgencyCards';
import { InfoLinks } from '@/features/public/InfoLinks';
import { useChat } from '@/features/chat/useChat';
import { usePublicPopularQuestions } from '@/features/popular-questions/popularQuestionsApi';
import { usePublicAgencies } from '@/features/public/publicAgenciesApi';
import { useState } from 'react';

export default function PublicPortal() {
  const {
    messages, input, setInput, isTyping, activeStepCount, currentSteps,
    streamingState, scrollRef, handleSend, handleRate, reset, cancelStream, hasMessages,
  } = useChat();
  const { data: popularQuestions } = usePublicPopularQuestions();
  const { data: publicAgencies } = usePublicAgencies();
  const [chatMode, setChatMode] = useState(false);

  const isStreaming = isTyping && streamingState.pipelineSteps.length > 0 && !streamingState.done;

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
          <span className="font-semibold text-foreground">AI Chatbot Portal กลาง</span>
        </div>
        <a href="/chat" className="text-xs text-primary hover:underline flex items-center gap-1 font-medium">
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
                  <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-primary/10 text-primary"><Bot className="h-4 w-4" /></div>
                  <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3 max-w-[75%]">
                    {isStreaming ? (
                      <StreamingProgress state={streamingState} />
                    ) : activeStepCount > 0 ? (
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
              {isTyping ? (
                <Button onClick={cancelStream} size="icon" variant="outline" className="rounded-xl shrink-0" title="ยกเลิก">
                  <X className="h-4 w-4" />
                </Button>
              ) : (
                <Button onClick={() => onSend()} size="icon" className="rounded-xl shrink-0" disabled={!input.trim()}>
                  <Send className="h-4 w-4" />
                </Button>
              )}
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

            {popularQuestions && popularQuestions.length > 0 && (
              <SuggestedQuestions questions={popularQuestions} onSelect={onSend} />
            )}

            {publicAgencies && publicAgencies.length > 0 && (
              <section className="w-full max-w-4xl mt-12">
                <h2 className="text-sm font-semibold text-foreground text-center mb-5">หน่วยงานที่เชื่อมต่อ</h2>
                <AgencyCards agencies={publicAgencies} />
              </section>
            )}
          </main>

          <footer className="border-t border-border py-6 px-6">
            <div className="max-w-xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">© 2568 AI Chatbot Portal กลาง</span>
              </div>
              <InfoLinks />
            </div>
          </footer>
        </>
      )}
    </div>
  );
}
