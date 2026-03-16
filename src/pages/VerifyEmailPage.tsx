import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/useAuth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Mail } from "lucide-react";

export default function VerifyEmailPage() {
  const navigate = useNavigate();
  const { user, isEmailVerified, refreshProfile } = useAuth();
  const [sending, setSending] = useState(false);

  // Auto-redirect when email becomes verified (e.g. user clicks link in another tab)
  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (_event) => {
      if (_event === "USER_UPDATED") {
        await refreshProfile();
      }
    });
    return () => subscription.unsubscribe();
  }, [refreshProfile]);

  useEffect(() => {
    if (isEmailVerified) {
      navigate("/", { replace: true });
    }
  }, [isEmailVerified, navigate]);

  const resend = async () => {
    if (!user?.email) return;
    setSending(true);
    const { error } = await supabase.auth.resend({ type: "signup", email: user.email });
    setSending(false);
    if (error) {
      toast.error(error.message);
    } else {
      toast.success("ส่งอีเมลยืนยันแล้ว!");
    }
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md text-center">
        <CardHeader className="space-y-4">
          <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
            <Mail className="w-8 h-8 text-primary" />
          </div>
          <CardTitle>ยืนยันอีเมลของคุณ</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            เราส่งลิงก์ยืนยันไปที่{" "}
            <strong className="text-foreground">{user?.email}</strong>{" "}
            กรุณาตรวจสอบกล่องจดหมาย (รวมถึงโฟลเดอร์ spam) และคลิกลิงก์เพื่อยืนยัน
          </p>
          <Button className="w-full" onClick={resend} disabled={sending}>
            {sending ? "กำลังส่ง..." : "ส่งอีเมลยืนยันอีกครั้ง"}
          </Button>
          <Button variant="ghost" className="w-full text-sm" onClick={signOut}>
            ออกจากระบบและใช้บัญชีอื่น
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
