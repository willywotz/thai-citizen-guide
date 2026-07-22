import { Send, X } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';

interface ChatInputProps {
  input: string;
  setInput: (value: string) => void;
  isTyping: boolean;
  onSend: () => void;
  onCancel: () => void;
}

export function ChatInput({ input, setInput, isTyping, onSend, onCancel }: ChatInputProps) {
  return (
    <div className="border-t border-border bg-card p-3">
      <div className="max-w-3xl mx-auto flex gap-2">
        <input value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && onSend()}
          placeholder="พิมพ์คำถามของคุณที่นี่..."
          className="flex-1 bg-background border border-input rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
        {isTyping ? (
          <Button onClick={onCancel} size="icon" variant="outline" className="rounded-xl shrink-0" title="ยกเลิก">
            <X className="h-4 w-4" />
          </Button>
        ) : (
          <Button onClick={onSend} size="icon" className="rounded-xl shrink-0" disabled={!input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
