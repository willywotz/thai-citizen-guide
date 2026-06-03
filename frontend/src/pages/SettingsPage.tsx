import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Save, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import { Navigate } from "react-router-dom";
import { getSettings, updateSettings } from "@/services/settingsApi";
import type { SettingField } from "@/types/settings";

const MASK = "*****";

const RESTART_FIELDS = new Set(["DATABASE_URL", "CORS_ORIGINS", "JWT_SECRET", "JWT_ALGORITHM"]);

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: SettingField;
  value: string;
  onChange: (v: string) => void;
}) {
  if (field.is_secret) {
    return (
      <Input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={MASK}
      />
    );
  }

  switch (field.field_type) {
    case "bool":
      return (
        <div className="flex items-center gap-2">
          <Switch
            checked={value === "true"}
            onCheckedChange={(checked) => onChange(checked ? "true" : "false")}
          />
          <span className="text-sm text-muted-foreground">{value}</span>
        </div>
      );
    case "int":
      return (
        <Input
          type="number"
          step="1"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "float":
      return (
        <Input
          type="number"
          step="0.01"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "list_str":
      return (
        <Textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          placeholder='["item1", "item2"]'
          className="font-mono text-xs"
        />
      );
    default:
      return (
        <Input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
}

export default function SettingsPage() {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
  });

  const [edited, setEdited] = useState<Record<string, string>>({});
  const [original, setOriginal] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!data) return;
    const orig: Record<string, string> = {};
    for (const g of data.groups) {
      for (const f of g.fields) {
        orig[f.key] = f.value;
      }
    }
    setOriginal(orig);
    setEdited(orig);
  }, [data]);

  const dirtyKeys = Object.keys(edited).filter((k) => edited[k] !== original[k]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const updates = dirtyKeys.map((key) => ({ key, value: edited[key] }));
      return updateSettings(updates);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success("ตั้งค่าเรียบร้อย");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleChange = useCallback((key: string, value: string) => {
    setEdited((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleReset = useCallback((key: string, defaultValue: string) => {
    setEdited((prev) => ({ ...prev, [key]: defaultValue }));
  }, []);

  if (!isAdmin) return <Navigate to="/chat" replace />;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  const groups = data?.groups ?? [];

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">ตั้งค่าระบบ</h1>
        <Button
          disabled={dirtyKeys.length === 0 || saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
        >
          {saveMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          <Save className="h-4 w-4 mr-2" />
          บันทึก ({dirtyKeys.length})
        </Button>
      </div>

      {groups.map((group) => (
        <Card key={group.group}>
          <CardHeader>
            <CardTitle className="text-lg">{group.group}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {group.fields.map((field) => (
              <div key={field.key} className="grid grid-cols-[200px_1fr_auto] gap-3 items-start">
                <Label className="text-sm font-mono pt-2">{field.key}</Label>
                <div className="space-y-1">
                  <FieldInput
                    field={field}
                    value={edited[field.key] ?? field.value}
                    onChange={(v) => handleChange(field.key, v)}
                  />
                  {RESTART_FIELDS.has(field.key) && (
                    <Alert variant="destructive" className="py-1.5 px-3">
                      <AlertDescription className="text-xs">
                        เปลี่ยนค่านี้แล้วต้อง restart server ถึงจะมีผล
                      </AlertDescription>
                    </Alert>
                  )}
                  {field.is_secret && (
                    <p className="text-[10px] text-muted-foreground">เว้นว่าง = ไม่เปลี่ยนแปลง</p>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  title="รีเซ็ตเป็นค่าเริ่มต้น"
                  onClick={() => handleReset(field.key, field.default_value)}
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}