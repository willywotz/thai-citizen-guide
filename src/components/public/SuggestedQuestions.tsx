import { ArrowUpRight } from 'lucide-react';
import type { Agency } from '@/types';

const agencyBgColors: Record<string, string> = {
  fda: 'bg-[hsl(var(--gov-fda)/0.1)]',
  revenue: 'bg-[hsl(var(--gov-revenue)/0.1)]',
  land: 'bg-[hsl(var(--gov-land)/0.1)]',
  dopa: 'bg-[hsl(var(--gov-dopa)/0.1)]',
};

const questionAgencyMap = [0, 1, 2, 3];

interface SuggestedQuestionsProps {
  questions: string[];
  agencies: Agency[];
  onSelect: (question: string) => void;
}

export function SuggestedQuestions({ questions, agencies, onSelect }: SuggestedQuestionsProps) {
  return (
    <div className="w-full max-w-xl">
      <p className="text-xs text-muted-foreground mb-3 text-center font-medium">คำถามยอดนิยม</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {questions.map((q, i) => {
          const agency = agencies[questionAgencyMap[i] ?? 0];
          return (
            <button
              key={i}
              onClick={() => onSelect(q)}
              className="group text-left text-sm bg-card border border-border rounded-2xl p-4 hover:bg-accent hover:border-primary/30 transition-all duration-200 hover:shadow-md flex items-start gap-3"
            >
              <span className={`text-lg shrink-0 mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center ${agencyBgColors[agency?.id] || ''}`}>
                {agency?.logo}
              </span>
              <span className="flex-1">{q}</span>
              <ArrowUpRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-0.5" />
            </button>
          );
        })}
      </div>
    </div>
  );
}
