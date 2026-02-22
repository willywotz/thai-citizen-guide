import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Send, Search, ArrowRight, ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { agencies, suggestedQuestions } from "@/data/mockData";

const agencyColors: Record<string, string> = {
  fda: "border-t-[hsl(var(--gov-fda))]",
  revenue: "border-t-[hsl(var(--gov-revenue))]",
  land: "border-t-[hsl(var(--gov-land))]",
  dopa: "border-t-[hsl(var(--gov-dopa))]",
};

const agencyBgColors: Record<string, string> = {
  fda: "bg-[hsl(var(--gov-fda)/0.1)]",
  revenue: "bg-[hsl(var(--gov-revenue)/0.1)]",
  land: "bg-[hsl(var(--gov-land)/0.1)]",
  dopa: "bg-[hsl(var(--gov-dopa)/0.1)]",
};

// Map suggested questions to agency icons
const questionAgencyMap = [0, 1, 2, 3]; // index into agencies

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
      <header className="border-b border-border bg-card/80 backdrop-blur-sm px-6 py-3 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl gov-gradient flex items-center justify-center text-white font-bold text-sm shadow-md">AI</div>
          <span className="font-semibold text-foreground">AI Portal กลาง</span>
        </div>
        <a href="/" className="text-xs text-primary hover:underline flex items-center gap-1 font-medium">
          เข้าสู่ระบบเจ้าหน้าที่ <ArrowRight className="w-3 h-3" />
        </a>
      </header>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-16">
        {/* Logo with glow */}
        <div className="relative mb-8">
          <div className="absolute inset-0 w-24 h-24 rounded-3xl gov-gradient opacity-30 blur-xl scale-125" />
          <div className="relative w-24 h-24 rounded-3xl gov-gradient flex items-center justify-center text-white text-4xl font-bold shadow-xl">
            AI
          </div>
        </div>

        {/* Title with gradient */}
        <h1 className="text-3xl md:text-4xl font-bold text-center mb-3 portal-gradient-text">
          ศูนย์บริการข้อมูลภาครัฐ
        </h1>
        <p className="text-sm md:text-base text-muted-foreground text-center max-w-lg mb-10 leading-relaxed">
          สอบถามข้อมูลจากหน่วยงานภาครัฐได้ครบในที่เดียว —{" "}
          <span className="text-foreground font-medium">Single Portal</span> เพื่อประชาชน
        </p>

        {/* Search */}
        <div className="w-full max-w-xl mb-12">
          <p className="text-xs text-muted-foreground mb-2 ml-1">ถามคำถามเกี่ยวกับบริการภาครัฐ</p>
          <div className="relative flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="พิมพ์คำถามของคุณ เช่น ขั้นตอนทำบัตรประชาชนใหม่..."
                className="w-full bg-card border border-input rounded-2xl pl-11 pr-4 py-4 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:border-primary shadow-sm transition-shadow focus:shadow-md"
              />
            </div>
            <Button onClick={() => handleSend()} size="icon" className="rounded-2xl h-[52px] w-[52px] shrink-0 shadow-sm" disabled={!input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Agencies */}
        <div className="flex flex-wrap justify-center gap-4 mb-12">
          {agencies.map((a, i) => (
            <div
              key={a.id}
              className={`group flex flex-col items-center gap-2 bg-card border border-border rounded-2xl p-5 w-36 transition-all duration-200 hover:scale-105 hover:shadow-lg border-t-[3px] ${agencyColors[a.id] || ""}`}
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <span className={`text-3xl w-12 h-12 rounded-xl flex items-center justify-center ${agencyBgColors[a.id] || ""}`}>
                {a.logo}
              </span>
              <span className="text-xs font-semibold text-foreground text-center">{a.shortName}</span>
              <span className="text-[10px] text-muted-foreground text-center leading-tight line-clamp-2">{a.description.slice(0, 40)}...</span>
            </div>
          ))}
        </div>

        {/* Suggested questions */}
        <div className="w-full max-w-xl">
          <p className="text-xs text-muted-foreground mb-3 text-center font-medium">คำถามยอดนิยม</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {suggestedQuestions.map((q, i) => {
              const agency = agencies[questionAgencyMap[i] ?? 0];
              return (
                <button
                  key={i}
                  onClick={() => handleSend(q)}
                  className="group text-left text-sm bg-card border border-border rounded-2xl p-4 hover:bg-accent hover:border-primary/30 transition-all duration-200 hover:shadow-md flex items-start gap-3"
                >
                  <span className={`text-lg shrink-0 mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center ${agencyBgColors[agency?.id] || ""}`}>
                    {agency?.logo}
                  </span>
                  <span className="flex-1">{q}</span>
                  <ArrowUpRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-0.5" />
                </button>
              );
            })}
          </div>
        </div>
      </main>

      {/* Footer */}
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
    </div>
  );
}
