import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Send, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { agencies, suggestedQuestions } from "@/data/mockData";

export default function PublicPortal() {
  const [input, setInput] = useState("");
  const navigate = useNavigate();

  const handleSend = (text?: string) => {
    const question = text || input.trim();
    if (!question) return;
    navigate(`/?q=${encodeURIComponent(question)}`);
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-card px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg gov-gradient flex items-center justify-center text-white font-bold text-sm">AI</div>
          <span className="font-semibold text-sm text-foreground">AI Portal กลาง</span>
        </div>
        <a href="/" className="text-xs text-primary hover:underline flex items-center gap-1">
          เข้าสู่ระบบเจ้าหน้าที่ <ArrowRight className="w-3 h-3" />
        </a>
      </header>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-12">
        <div className="w-20 h-20 rounded-2xl gov-gradient flex items-center justify-center text-white text-3xl font-bold mb-6">AI</div>
        <h1 className="text-2xl md:text-3xl font-bold text-foreground text-center mb-2">ศูนย์บริการข้อมูลภาครัฐ</h1>
        <p className="text-sm text-muted-foreground text-center max-w-lg mb-8">
          สอบถามข้อมูลจากหน่วยงานภาครัฐได้ครบในที่เดียว — สำนักงาน อย., กรมสรรพากร, กรมการปกครอง, กรมที่ดิน
        </p>

        {/* Search */}
        <div className="w-full max-w-xl flex gap-2 mb-10">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="พิมพ์คำถามของคุณ เช่น ขั้นตอนทำบัตรประชาชนใหม่..."
            className="flex-1 bg-card border border-input rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <Button onClick={() => handleSend()} size="icon" className="rounded-xl h-11 w-11 shrink-0" disabled={!input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </div>

        {/* Agencies */}
        <div className="flex flex-wrap justify-center gap-4 mb-10">
          {agencies.map((a) => (
            <div key={a.id} className="flex flex-col items-center gap-1.5 bg-card border border-border rounded-xl p-4 w-32 hover:border-primary/30 transition-colors">
              <span className="text-3xl">{a.logo}</span>
              <span className="text-xs font-medium text-foreground text-center">{a.shortName}</span>
              <span className="text-[10px] text-muted-foreground">{a.connectionType}</span>
            </div>
          ))}
        </div>

        {/* Suggested questions */}
        <div className="w-full max-w-xl">
          <p className="text-xs text-muted-foreground mb-3 text-center">คำถามยอดนิยม</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {suggestedQuestions.map((q, i) => (
              <button
                key={i}
                onClick={() => handleSend(q)}
                className="text-left text-sm bg-card border border-border rounded-xl p-3 hover:bg-accent hover:border-primary/30 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-4 text-center text-xs text-muted-foreground">
        © 2568 AI Portal กลาง — ระบบบูรณาการข้อมูลหน่วยงานภาครัฐ
      </footer>
    </div>
  );
}
