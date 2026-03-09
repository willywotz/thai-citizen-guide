import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { X, Plus, Upload, Loader2, Trash2 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "sonner";
import type { Agency, ApiEndpoint } from "@/types/agency";

const protocolInfo: Record<string, string> = {
  MCP: "Model Context Protocol — มาตรฐานการเชื่อมต่อ AI กับเครื่องมือภายนอก รองรับ tools/list, tools/call, resources/read",
  A2A: "Agent-to-Agent Protocol — มาตรฐานการสื่อสารระหว่าง AI Agent ผ่าน Agent Card exchange",
  API: "REST API — การเชื่อมต่อผ่าน HTTP endpoint มาตรฐาน พร้อม authentication",
};

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agency?: Agency | null;
  onSave: (data: Partial<Agency>) => void;
  saving?: boolean;
}

export function AgencyFormDialog({ open, onOpenChange, agency, onSave, saving }: Props) {
  const [name, setName] = useState("");
  const [shortName, setShortName] = useState("");
  const [logo, setLogo] = useState("🏢");
  const [description, setDescription] = useState("");
  const [connectionType, setConnectionType] = useState<"MCP" | "API" | "A2A">("API");
  const [endpointUrl, setEndpointUrl] = useState("");
  const [color, setColor] = useState("hsl(213 70% 45%)");
  const [scopeInput, setScopeInput] = useState("");
  const [dataScope, setDataScope] = useState<string[]>([]);
  const [status, setStatus] = useState<"active" | "inactive">("active");

  // API-specific fields
  const [authMethod, setAuthMethod] = useState("api_key");
  const [authHeader, setAuthHeader] = useState("");
  const [basePath, setBasePath] = useState("");
  const [rateLimitRpm, setRateLimitRpm] = useState<string>("");
  const [requestFormat, setRequestFormat] = useState("json");
  const [apiEndpoints, setApiEndpoints] = useState<ApiEndpoint[]>([]);
  const [parsing, setParsing] = useState(false);

  useEffect(() => {
    if (agency) {
      setName(agency.name);
      setShortName(agency.shortName);
      setLogo(agency.logo);
      setDescription(agency.description);
      setConnectionType(agency.connectionType);
      setEndpointUrl(agency.endpointUrl || "");
      setColor(agency.color);
      setDataScope(agency.dataScope);
      setStatus(agency.status);
      setAuthMethod(agency.authMethod || "api_key");
      setAuthHeader(agency.authHeader || "");
      setBasePath(agency.basePath || "");
      setRateLimitRpm(agency.rateLimitRpm ? String(agency.rateLimitRpm) : "");
      setRequestFormat(agency.requestFormat || "json");
      setApiEndpoints(agency.apiEndpoints || []);
    } else {
      setName(""); setShortName(""); setLogo("🏢"); setDescription("");
      setConnectionType("API"); setEndpointUrl(""); setColor("hsl(213 70% 45%)");
      setDataScope([]); setStatus("active");
      setAuthMethod("api_key"); setAuthHeader(""); setBasePath("");
      setRateLimitRpm(""); setRequestFormat("json"); setApiEndpoints([]);
    }
  }, [agency, open]);

  const addScope = () => {
    const v = scopeInput.trim();
    if (v && !dataScope.includes(v)) {
      setDataScope([...dataScope, v]);
      setScopeInput("");
    }
  };

  const addEndpoint = () => {
    setApiEndpoints([...apiEndpoints, { method: "GET", path: "", description: "" }]);
  };

  const updateEndpoint = (index: number, field: keyof ApiEndpoint, value: string) => {
    setApiEndpoints(apiEndpoints.map((ep, i) => i === index ? { ...ep, [field]: value } : ep));
  };

  const removeEndpoint = (index: number) => {
    setApiEndpoints(apiEndpoints.filter((_, i) => i !== index));
  };

  const handleSpecUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setParsing(true);
      const specText = await file.text();

      const { data, error } = await supabase.functions.invoke('parse-api-spec', {
        body: { specText },
      });

      if (error) throw new Error(error.message);
      if (!data?.success || !data?.data) throw new Error('Failed to parse spec');

      const parsed = data.data;
      if (parsed.auth_method) setAuthMethod(parsed.auth_method);
      if (parsed.auth_header) setAuthHeader(parsed.auth_header);
      if (parsed.base_path) setBasePath(parsed.base_path);
      if (parsed.rate_limit_rpm) setRateLimitRpm(String(parsed.rate_limit_rpm));
      if (parsed.request_format) setRequestFormat(parsed.request_format);
      if (parsed.endpoints?.length) setApiEndpoints(parsed.endpoints);

      toast.success(`สำเร็จ! พบ ${parsed.endpoints?.length || 0} endpoints`);
    } catch (err: any) {
      toast.error("ไม่สามารถ parse spec ได้: " + (err.message || "Unknown error"));
    } finally {
      setParsing(false);
      e.target.value = "";
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !shortName) return;
    onSave({
      name, shortName, logo, description, connectionType, endpointUrl, color, dataScope, status,
      ...(connectionType === "API" ? {
        authMethod,
        authHeader,
        basePath,
        rateLimitRpm: rateLimitRpm ? parseInt(rateLimitRpm) : null,
        requestFormat,
        apiEndpoints: apiEndpoints.filter(ep => ep.path),
      } : {}),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{agency ? "แก้ไขหน่วยงาน" : "เพิ่มหน่วยงานใหม่"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-[auto_1fr] gap-4 items-start">
            <div>
              <Label>โลโก้</Label>
              <Input value={logo} onChange={(e) => setLogo(e.target.value)} className="w-16 text-center text-2xl" />
            </div>
            <div className="space-y-2">
              <Label>ชื่อหน่วยงาน *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="ชื่อเต็มหน่วยงาน" required />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>ชื่อย่อ *</Label>
              <Input value={shortName} onChange={(e) => setShortName(e.target.value)} placeholder="ชื่อย่อ" required />
            </div>
            <div className="space-y-2">
              <Label>สถานะ</Label>
              <Select value={status} onValueChange={(v) => setStatus(v as "active" | "inactive")}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>คำอธิบาย</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </div>

          <div className="space-y-2">
            <Label>ประเภทการเชื่อมต่อ</Label>
            <Select value={connectionType} onValueChange={(v) => setConnectionType(v as "MCP" | "API" | "A2A")}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="MCP">MCP (Model Context Protocol)</SelectItem>
                <SelectItem value="API">API (REST)</SelectItem>
                <SelectItem value="A2A">A2A (Agent-to-Agent)</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-[11px] text-muted-foreground">{protocolInfo[connectionType]}</p>
          </div>

          <div className="space-y-2">
            <Label>Endpoint URL</Label>
            <Input value={endpointUrl} onChange={(e) => setEndpointUrl(e.target.value)} placeholder="https://api.example.go.th/v1" />
          </div>

          {/* API-specific fields */}
          {connectionType === "API" && (
            <div className="space-y-4 border border-border rounded-lg p-4 bg-muted/30">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-foreground">⚙️ API Configuration</p>
                <label className="cursor-pointer">
                  <input type="file" accept=".json,.yaml,.yml" className="hidden" onChange={handleSpecUpload} disabled={parsing} />
                  <Button type="button" variant="outline" size="sm" className="gap-1.5" asChild disabled={parsing}>
                    <span>
                      {parsing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                      {parsing ? "กำลัง Parse..." : "Upload API Spec"}
                    </span>
                  </Button>
                </label>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Auth Method</Label>
                  <Select value={authMethod} onValueChange={setAuthMethod}>
                    <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="api_key">API Key</SelectItem>
                      <SelectItem value="oauth2">OAuth 2.0</SelectItem>
                      <SelectItem value="basic_auth">Basic Auth</SelectItem>
                      <SelectItem value="none">ไม่มี</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Auth Header</Label>
                  <Input value={authHeader} onChange={(e) => setAuthHeader(e.target.value)} placeholder="X-API-Key" className="h-9" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Base Path</Label>
                  <Input value={basePath} onChange={(e) => setBasePath(e.target.value)} placeholder="/api/v1" className="h-9" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Rate Limit (RPM)</Label>
                  <Input type="number" value={rateLimitRpm} onChange={(e) => setRateLimitRpm(e.target.value)} placeholder="60" className="h-9" />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs">Request Format</Label>
                <Select value={requestFormat} onValueChange={setRequestFormat}>
                  <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="json">JSON</SelectItem>
                    <SelectItem value="xml">XML</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Endpoints list */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs">API Endpoints</Label>
                  <Button type="button" variant="ghost" size="sm" className="h-7 text-xs gap-1" onClick={addEndpoint}>
                    <Plus className="h-3 w-3" /> เพิ่ม
                  </Button>
                </div>
                {apiEndpoints.map((ep, i) => (
                  <div key={i} className="flex gap-2 items-start">
                    <Select value={ep.method} onValueChange={(v) => updateEndpoint(i, 'method', v)}>
                      <SelectTrigger className="h-8 w-[90px] text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {["GET", "POST", "PUT", "DELETE", "PATCH"].map((m) => (
                          <SelectItem key={m} value={m}>{m}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Input value={ep.path} onChange={(e) => updateEndpoint(i, 'path', e.target.value)} placeholder="/path" className="h-8 text-xs flex-1" />
                    <Input value={ep.description} onChange={(e) => updateEndpoint(i, 'description', e.target.value)} placeholder="คำอธิบาย" className="h-8 text-xs flex-1" />
                    <Button type="button" variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={() => removeEndpoint(i)}>
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  </div>
                ))}
                {apiEndpoints.length === 0 && (
                  <p className="text-[11px] text-muted-foreground text-center py-2">ยังไม่มี endpoint — กดเพิ่ม หรือ Upload API Spec</p>
                )}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>สี</Label>
              <Input value={color} onChange={(e) => setColor(e.target.value)} placeholder="hsl(213 70% 45%)" />
            </div>
          </div>

          <div className="space-y-2">
            <Label>ขอบเขตข้อมูล</Label>
            <div className="flex gap-2">
              <Input
                value={scopeInput}
                onChange={(e) => setScopeInput(e.target.value)}
                placeholder="เพิ่มขอบเขต แล้วกด Enter"
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addScope(); } }}
              />
              <Button type="button" variant="outline" size="sm" onClick={addScope}>เพิ่ม</Button>
            </div>
            <div className="flex flex-wrap gap-1 mt-1">
              {dataScope.map((s, i) => (
                <Badge key={i} variant="secondary" className="text-[10px] gap-1">
                  {s}
                  <X className="h-3 w-3 cursor-pointer" onClick={() => setDataScope(dataScope.filter((_, j) => j !== i))} />
                </Badge>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>ยกเลิก</Button>
            <Button type="submit" disabled={saving || !name || !shortName}>
              {saving ? "กำลังบันทึก..." : agency ? "บันทึก" : "เพิ่มหน่วยงาน"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
