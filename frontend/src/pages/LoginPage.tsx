import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "@/shared/lib/apiClient";
import { useAuth, type AuthUser } from "@/hooks/useAuth";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { toast } from "sonner";
import { LogIn } from "lucide-react";
import { AppLogo } from "@/shared/components/ui/AppLogo";

export default function LoginPage() {
  const navigate = useNavigate();
  const { user, isLoading, setAuth } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  // Redirect if already logged in
  useEffect(() => {
    if (!isLoading && user) {
      navigate("/chat", { replace: true });
    }
  }, [user, isLoading, navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.post<{ access_token: string; user: AuthUser }>("/api/v1/auth/login", {
        email,
        password,
      });
      setAuth(res.access_token, res.user);
      toast.success("เข้าสู่ระบบสำเร็จ");
      navigate("/chat", { replace: true });
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "เข้าสู่ระบบไม่สำเร็จ");
    } finally {
      setLoading(false);
    }
  };

  if (!isLoading && user) return null;

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center space-y-2">
          <AppLogo className="w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold text-lg mx-auto" />
          <CardTitle className="text-xl">เข้าสู่ระบบ Admin</CardTitle>
          <p className="text-sm text-muted-foreground">
            AI Portal กลาง — ระบบบูรณาการข้อมูลหน่วยงานภาครัฐ
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">อีเมล</Label>
              <Input
                id="email"
                type="email"
                placeholder="admin@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">รหัสผ่าน</Label>
                <Link to="/forgot-password" className="text-xs text-primary hover:underline">
                  ลืมรหัสผ่าน?
                </Link>
              </div>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              <LogIn className="h-4 w-4 mr-2" />
              {loading ? "กำลังเข้าสู่ระบบ..." : "เข้าสู่ระบบ"}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm text-muted-foreground">
            ยังไม่มีบัญชี?{" "}
            <Link to="/signup" className="text-primary hover:underline">
              สมัครสมาชิก
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
