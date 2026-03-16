import { useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { toast } from "sonner";
import { ROLE_LABELS, ROLE_COLORS } from "@/types/auth";

export default function AccountPage() {
  const { user, profile, roles, refreshProfile, isEmailVerified } = useAuth();
  const [displayName, setDisplayName] = useState(profile?.displayName ?? "");
  const [savingProfile, setSavingProfile] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  const [linkingProvider, setLinkingProvider] = useState<string | null>(null);

  const initials = (profile?.displayName || user?.email || "U")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const handleSaveProfile = async () => {
    if (!displayName.trim()) return;
    setSavingProfile(true);
    const { error } = await supabase
      .from("profiles")
      .update({ display_name: displayName.trim(), updated_at: new Date().toISOString() })
      .eq("id", user!.id);
    setSavingProfile(false);
    if (error) {
      toast.error(error.message);
    } else {
      await refreshProfile();
      toast.success("อัปเดตโปรไฟล์แล้ว");
    }
  };

  const handleChangePassword = async () => {
    if (newPassword.length < 8) {
      toast.error("รหัสผ่านใหม่ต้องมีอย่างน้อย 8 ตัวอักษร");
      return;
    }
    setChangingPassword(true);
    const { error } = await supabase.auth.updateUser({ password: newPassword });
    setChangingPassword(false);
    if (error) {
      toast.error(error.message);
    } else {
      setCurrentPassword("");
      setNewPassword("");
      toast.success("เปลี่ยนรหัสผ่านสำเร็จ");
    }
  };

  const handleLinkOAuth = async (provider: "google" | "github") => {
    setLinkingProvider(provider);
    const { error } = await supabase.auth.linkIdentity({ provider });
    setLinkingProvider(null);
    if (error) toast.error(error.message);
  };

  const handleResendVerification = async () => {
    if (!user?.email) return;
    const { error } = await supabase.auth.resend({ type: "signup", email: user.email });
    if (error) toast.error(error.message);
    else toast.success("ส่งอีเมลยืนยันแล้ว");
  };

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">บัญชีของฉัน</h1>

      {/* Profile section */}
      <Card>
        <CardHeader>
          <CardTitle>ข้อมูลโปรไฟล์</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <Avatar className="h-16 w-16">
              <AvatarImage src={profile?.avatarUrl ?? undefined} />
              <AvatarFallback className="text-xl bg-primary text-primary-foreground">
                {initials}
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="font-medium">{profile?.displayName || "—"}</p>
              <p className="text-sm text-muted-foreground">{user?.email}</p>
              <div className="flex gap-1 mt-1">
                {roles.map((role) => (
                  <span
                    key={role}
                    className={`text-xs px-2 py-0.5 rounded-full border font-medium ${ROLE_COLORS[role]}`}
                  >
                    {ROLE_LABELS[role]}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-1">
            <Label>ชื่อแสดง</Label>
            <div className="flex gap-2">
              <Input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="ชื่อ-นามสกุล"
              />
              <Button onClick={handleSaveProfile} disabled={savingProfile}>
                {savingProfile ? "กำลังบันทึก..." : "บันทึก"}
              </Button>
            </div>
          </div>

          {/* Email verification status */}
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">อีเมล:</span>
            <span>{user?.email}</span>
            {isEmailVerified ? (
              <Badge variant="outline" className="text-green-700 border-green-200 bg-green-50">ยืนยันแล้ว</Badge>
            ) : (
              <>
                <Badge variant="outline" className="text-amber-700 border-amber-200 bg-amber-50">ยังไม่ยืนยัน</Badge>
                <Button variant="link" className="h-auto p-0 text-xs" onClick={handleResendVerification}>
                  ส่งอีกครั้ง
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* OAuth linking */}
      <Card>
        <CardHeader>
          <CardTitle>บัญชีที่เชื่อมต่อ</CardTitle>
          <CardDescription>เชื่อมต่อบัญชี OAuth เพื่อเข้าสู่ระบบได้หลายวิธี</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {(["google", "github"] as const).map((provider) => {
            const isConnected = profile?.authProvider === provider;
            return (
              <div key={provider} className="flex items-center justify-between">
                <span className="text-sm capitalize font-medium">{provider === "google" ? "Google" : "GitHub"}</span>
                {isConnected ? (
                  <Badge variant="outline" className="text-green-700 border-green-200 bg-green-50">เชื่อมต่อแล้ว</Badge>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleLinkOAuth(provider)}
                    disabled={linkingProvider !== null}
                  >
                    {linkingProvider === provider ? "กำลังเชื่อมต่อ..." : "เชื่อมต่อ"}
                  </Button>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Password change (only for email provider) */}
      {profile?.authProvider === "email" && (
        <Card>
          <CardHeader>
            <CardTitle>เปลี่ยนรหัสผ่าน</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <Label>รหัสผ่านใหม่</Label>
              <Input
                type="password"
                placeholder="อย่างน้อย 8 ตัวอักษร"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                minLength={8}
              />
            </div>
            <Button onClick={handleChangePassword} disabled={changingPassword || !newPassword}>
              {changingPassword ? "กำลังเปลี่ยน..." : "เปลี่ยนรหัสผ่าน"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
