import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search, CheckCircle, XCircle, Loader2, Trash2 } from "lucide-react";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { useChatHistory } from "@/hooks/useChatHistory";
import { ConversationDetailDialog } from "@/components/history/ConversationDetailDialog";
import { deleteConversation } from "@/services/historyApi";
import type { HistoryItem } from "@/services/historyApi";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

export default function HistoryPage() {
  const [search, setSearch] = useState("");
  const [filterAgency, setFilterAgency] = useState<string | null>(null);
  const [selectedConv, setSelectedConv] = useState<HistoryItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<HistoryItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { data: conversations = [], isLoading } = useChatHistory(search, filterAgency || undefined);
  const queryClient = useQueryClient();

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    const ok = await deleteConversation(deleteTarget.id);
    setDeleting(false);
    setDeleteTarget(null);
    if (ok) {
      toast.success("ลบสนทนาเรียบร้อย");
      queryClient.invalidateQueries({ queryKey: ['chatHistory'] });
    } else {
      toast.error("ไม่สามารถลบได้ กรุณาลองใหม่");
    }
  };

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
            <Card key={conv.id} className="cursor-pointer hover:bg-accent/30 transition-colors" onClick={() => setSelectedConv(conv)}>
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
                  <div className="flex items-center gap-1 shrink-0">
                    <span className="text-[10px] text-muted-foreground">{conv.date}</span>
                    <button
                      onClick={(e) => { e.stopPropagation(); setDeleteTarget(conv); }}
                      className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                      aria-label="ลบสนทนา"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
          {conversations.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-12">ไม่พบผลลัพธ์</p>
          )}
        </div>
      )}

      <ConversationDetailDialog
        conversation={selectedConv}
        open={!!selectedConv}
        onOpenChange={(open) => { if (!open) setSelectedConv(null); }}
      />

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>ยืนยันการลบ</AlertDialogTitle>
            <AlertDialogDescription>
              ต้องการลบสนทนา "{deleteTarget?.title}" หรือไม่? การดำเนินการนี้ไม่สามารถย้อนกลับได้
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>ยกเลิก</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              ลบ
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
