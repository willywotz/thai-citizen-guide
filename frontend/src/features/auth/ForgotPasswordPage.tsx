import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/shared/lib/apiClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { toast } from "sonner";
import { Mail, Copy } from "lucide-react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [resetToken, setResetToken] = useState<string | null>(null);

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.post<{ message: string; reset_token?: string }>(
        "/api/v1/auth/forgot-password",
        { email }
      );
      setSent(true);
      // In development the backend returns the token directly
      if (res.reset_token) setResetToken(res.reset_token);
      toast.success(res.message);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "เกิดข้อผิดพลาด");
    } finally {
      setLoading(false);
    }
  };

  const copyToken = () => {
    if (resetToken) {
      navigator.clipboard.writeText(resetToken);
      toast.success("คัดลอก token แล้ว");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center space-y-2">
          <CardTitle className="text-xl">ลืมรหัสผ่าน</CardTitle>
          <p className="text-sm text-muted-foreground">กรอกอีเมลเพื่อรับ token รีเซ็ตรหัสผ่าน</p>
        </CardHeader>
        <CardContent>
          {sent ? (
            <div className="text-center space-y-4">
              <Mail className="h-12 w-12 mx-auto text-primary" />
              <p className="text-sm text-muted-foreground">
                ดำเนินการเรียบร้อยสำหรับ <strong>{email}</strong>
              </p>

              {resetToken && (
                <div className="bg-muted rounded-lg p-3 text-left space-y-2">
                  <p className="text-xs text-muted-foreground font-medium">
                    Reset Token (ใช้ในหน้า Reset Password):
                  </p>
                  <div className="flex items-center gap-2">
                    <code className="text-xs break-all flex-1 text-foreground">{resetToken}</code>
                    <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0" onClick={copyToken}>
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              )}

              <Link to="/reset-password" className="text-sm text-primary hover:underline block">
                ไปหน้าตั้งรหัสผ่านใหม่
              </Link>
              <Link to="/login" className="text-sm text-muted-foreground hover:underline block">
                กลับไปหน้าเข้าสู่ระบบ
              </Link>
            </div>
          ) : (
            <form onSubmit={handleReset} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">อีเมล</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "กำลังส่ง..." : "ขอ Token รีเซ็ต"}
              </Button>
              <div className="text-center">
                <Link to="/login" className="text-sm text-muted-foreground hover:text-primary">
                  กลับไปหน้าเข้าสู่ระบบ
                </Link>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
