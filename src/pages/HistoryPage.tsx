import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { useChatHistory } from "@/hooks/useChatHistory";

export default function HistoryPage() {
  const [search, setSearch] = useState("");
  const [filterAgency, setFilterAgency] = useState<string | null>(null);
  const { data: conversations = [], isLoading } = useChatHistory(search, filterAgency || undefined);

  const allAgencies = ['อย.', 'กรมสรรพากร', 'กรมการปกครอง', 'กรมที่ดิน'];

  return (
    <div className="p-4 md:p-6 space-y-4">
      <h2 className="text-lg font-semibold text-foreground">ประวัติการสนทนา</h2>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="ค้นหาการสนทนา..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex gap-1.5">
          <button
            onClick={() => setFilterAgency(null)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${!filterAgency ? 'bg-primary text-primary-foreground border-primary' : 'border-border text-muted-foreground hover:bg-accent'}`}
          >
            ทั้งหมด
          </button>
          {allAgencies.map((a) => (
            <button key={a}
              onClick={() => setFilterAgency(filterAgency === a ? null : a)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${filterAgency === a ? 'bg-primary text-primary-foreground border-primary' : 'border-border text-muted-foreground hover:bg-accent'}`}
            >
              {a}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      )}

      {/* Conversation list */}
      {!isLoading && (
        <div className="space-y-2">
          {conversations.map((conv) => (
            <Card key={conv.id} className="cursor-pointer hover:bg-accent/30 transition-colors">
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      {conv.status === 'success' ? (
                        <CheckCircle className="h-4 w-4 text-green-600 shrink-0" />
                      ) : (
                        <XCircle className="h-4 w-4 text-destructive shrink-0" />
                      )}
                      <h3 className="text-sm font-medium text-foreground truncate">{conv.title}</h3>
                    </div>
                    <p className="text-xs text-muted-foreground line-clamp-1 ml-6">{conv.preview}</p>
                    <div className="flex items-center gap-2 mt-2 ml-6 flex-wrap">
                      {conv.agencies.map((a, i) => (
                        <Badge key={i} variant="outline" className="text-[10px]">{a}</Badge>
                      ))}
                      {conv.messageCount && (
                        <span className="text-[10px] text-muted-foreground">{conv.messageCount} ข้อความ</span>
                      )}
                      {conv.responseTime && (
                        <span className="text-[10px] text-muted-foreground">⏱ {conv.responseTime}</span>
                      )}
                    </div>
                  </div>
                  <span className="text-[10px] text-muted-foreground shrink-0">{conv.date}</span>
                </div>
              </CardContent>
            </Card>
          ))}
          {conversations.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-12">ไม่พบผลลัพธ์</p>
          )}
        </div>
      )}
    </div>
  );
}
