import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { MailWarning, X } from "lucide-react";

export function EmailVerificationBanner() {
  const { user, isEmailVerified, profile } = useAuth();
  const [dismissed, setDismissed] = useState(false);
  const [sending, setSending] = useState(false);

  // Only show for email provider accounts that are not yet verified
  if (!user || isEmailVerified || dismissed || profile?.authProvider !== "email") {
    return null;
  }

  const resend = async () => {
    if (!user.email) return;
    setSending(true);
    const { error } = await supabase.auth.resend({ type: "signup", email: user.email });
    setSending(false);
    if (error) {
      toast.error(error.message);
    } else {
      toast.success("ส่งอีเมลยืนยันแล้ว กรุณาตรวจสอบกล่องจดหมาย");
    }
  };

  return (
    <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-2 flex items-center justify-between gap-3 text-sm">
      <div className="flex items-center gap-2 text-yellow-800">
        <MailWarning className="h-4 w-4 shrink-0" />
        <span>กรุณายืนยันอีเมล <strong>{user.email}</strong> เพื่อใช้งานฟีเจอร์ทั้งหมด</span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs border-yellow-400 text-yellow-800 hover:bg-yellow-100"
          onClick={resend}
          disabled={sending}
        >
          {sending ? "กำลังส่ง..." : "ส่งอีเมลใหม่"}
        </Button>
        <button
          onClick={() => setDismissed(true)}
          className="text-yellow-600 hover:text-yellow-900"
          aria-label="ปิด"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
