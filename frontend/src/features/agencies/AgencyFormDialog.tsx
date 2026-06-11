import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/components/ui/select";
import { Badge } from "@/shared/components/ui/badge";
import { X } from "lucide-react";
import { api } from "@/shared/lib/apiClient";
import { toast } from "sonner";
import type { Agency, AgencyLifecycleStatus, ApiEndpoint, ResponseField, ApiHeader } from "@/shared/types/agency";
import { AgencyApiFields } from "./AgencyApiFields";
import { AgencyHeadersEditor } from "./AgencyHeadersEditor";
import {
  DEFAULT_FORM_STATE,
  PROTOCOL_INFO,
  agencyToFormState,
  buildSavePayload,
  isFormValid,
  parseExpectedPayload,
  type ParseSpecResponse,
} from "./agencyForm";

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
  const [status, setStatus] = useState<AgencyLifecycleStatus>("active");

  // API-specific fields
  const [authMethod, setAuthMethod] = useState("api_key");
  const [authHeader, setAuthHeader] = useState("");
  const [basePath, setBasePath] = useState("");
  const [rateLimitRpm, setRateLimitRpm] = useState<string>("");
  const [requestFormat, setRequestFormat] = useState("json");
  const [apiEndpoints, setApiEndpoints] = useState<ApiEndpoint[]>([]);
  const [responseSchema, setResponseSchema] = useState<ResponseField[]>([]);
  const [expectedPayload, setExpectedPayload] = useState<string>("");
  const [expectedPayloadError, setExpectedPayloadError] = useState(false);
  const [parsedPayload, setParsedPayload] = useState<Record<string, unknown> | null>(null);
  const [parsing, setParsing] = useState(false);
  const [apiSpecRaw, setApiSpecRaw] = useState<string>("");
  const [apiHeaders, setApiHeaders] = useState<ApiHeader[]>([]);

  useEffect(() => {
    if (agency) {
      const s = agencyToFormState(agency);
      setName(s.name);
      setShortName(s.shortName);
      setLogo(s.logo);
      setDescription(s.description);
      setConnectionType(s.connectionType);
      setEndpointUrl(s.endpointUrl);
      setColor(s.color);
      setDataScope(s.dataScope);
      setStatus(s.status);
      setAuthMethod(s.authMethod);
      setAuthHeader(s.authHeader);
      setBasePath(s.basePath);
      setRateLimitRpm(s.rateLimitRpm);
      setRequestFormat(s.requestFormat);
      setApiEndpoints(s.apiEndpoints);
      setResponseSchema(s.responseSchema);
      setExpectedPayload(s.expectedPayload);
      setExpectedPayloadError(false);
      setApiSpecRaw(s.apiSpecRaw);
      setParsedPayload(agency.expectedPayload ?? null);
      setApiHeaders(s.apiHeaders);
    } else {
      const s = DEFAULT_FORM_STATE;
      setName(s.name); setShortName(s.shortName); setLogo(s.logo); setDescription(s.description);
      setConnectionType(s.connectionType); setEndpointUrl(s.endpointUrl); setColor(s.color);
      setDataScope(s.dataScope); setStatus(s.status);
      setAuthMethod(s.authMethod); setAuthHeader(s.authHeader); setBasePath(s.basePath);
      setRateLimitRpm(s.rateLimitRpm); setRequestFormat(s.requestFormat); setApiEndpoints(s.apiEndpoints);
      setResponseSchema(s.responseSchema); setExpectedPayload(s.expectedPayload); setExpectedPayloadError(false);
      setApiSpecRaw(s.apiSpecRaw); setParsedPayload(null); setApiHeaders(s.apiHeaders);
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
    setApiEndpoints(apiEndpoints.map((ep, i) => (i === index ? { ...ep, [field]: value } : ep)));
  };

  const removeEndpoint = (index: number) => {
    setApiEndpoints(apiEndpoints.filter((_, i) => i !== index));
  };

  const addApiHeader = () => {
    setApiHeaders([...apiHeaders, { name: "", value: "" }]);
  };

  const updateApiHeader = (index: number, field: keyof ApiHeader, value: string) => {
    setApiHeaders(apiHeaders.map((h, i) => (i === index ? { ...h, [field]: value } : h)));
  };

  const removeApiHeader = (index: number) => {
    setApiHeaders(apiHeaders.filter((_, i) => i !== index));
  };

  const addResponseField = () => {
    setResponseSchema([...responseSchema, { field: "", type: "string", description: "" }]);
  };

  const updateResponseField = (index: number, field: keyof ResponseField, value: string) => {
    setResponseSchema(responseSchema.map((r, i) => (i === index ? { ...r, [field]: value } : r)));
  };

  const removeResponseField = (index: number) => {
    setResponseSchema(responseSchema.filter((_, i) => i !== index));
  };

  const handleSpecUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setParsing(true);
      const specText = await file.text();

      const data = await api.post<ParseSpecResponse>("/api/v1/agencies/parse-spec", { spec_text: specText });

      if (!data?.success || !data?.data) throw new Error("Failed to parse spec");

      const parsed = data.data;
      if (parsed.auth_method) setAuthMethod(parsed.auth_method);
      if (parsed.auth_header) setAuthHeader(parsed.auth_header);
      if (parsed.base_path) setBasePath(parsed.base_path);
      if (parsed.rate_limit_rpm) setRateLimitRpm(String(parsed.rate_limit_rpm));
      if (parsed.request_format) setRequestFormat(parsed.request_format);
      if (parsed.endpoints?.length) setApiEndpoints(parsed.endpoints);
      if (parsed.response_schema?.length) setResponseSchema(parsed.response_schema);
      if (parsed.expected_payload) setExpectedPayload(JSON.stringify(parsed.expected_payload, null, 2));
      setApiSpecRaw(specText);
      toast.success(`สำเร็จ! พบ ${parsed.endpoints?.length ?? 0} endpoints, ${parsed.response_schema?.length ?? 0} response fields`);
    } catch (err: unknown) {
      toast.error("ไม่สามารถ parse spec ได้: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setParsing(false);
      e.target.value = "";
    }
  };

  useEffect(() => {
    const { value, error } = parseExpectedPayload(expectedPayload);
    setParsedPayload(value);
    setExpectedPayloadError(error);
  }, [expectedPayload]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isFormValid({ name, shortName })) return;

    const formState = {
      name, shortName, logo, description, connectionType, endpointUrl, color,
      scopeInput, dataScope, status,
      authMethod, authHeader, basePath, rateLimitRpm, requestFormat,
      apiEndpoints, responseSchema, expectedPayload, apiSpecRaw, apiHeaders,
    };

    onSave(buildSavePayload(formState, parsedPayload));
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
              <Select value={status} onValueChange={(v) => setStatus(v as AgencyLifecycleStatus)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="disabled">Disabled</SelectItem>
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
            <p className="text-[11px] text-muted-foreground">{PROTOCOL_INFO[connectionType]}</p>
          </div>

          <div className="space-y-2">
            <Label>Endpoint URL</Label>
            <Input value={endpointUrl} onChange={(e) => setEndpointUrl(e.target.value)} placeholder="https://api.example.go.th/v1" />
          </div>

          <AgencyHeadersEditor
            headers={apiHeaders}
            onAdd={addApiHeader}
            onUpdate={updateApiHeader}
            onRemove={removeApiHeader}
          />

          {connectionType === "API" && (
            <AgencyApiFields
              authMethod={authMethod}
              onAuthMethodChange={setAuthMethod}
              authHeader={authHeader}
              onAuthHeaderChange={setAuthHeader}
              basePath={basePath}
              onBasePathChange={setBasePath}
              rateLimitRpm={rateLimitRpm}
              onRateLimitRpmChange={setRateLimitRpm}
              requestFormat={requestFormat}
              onRequestFormatChange={setRequestFormat}
              apiEndpoints={apiEndpoints}
              onAddEndpoint={addEndpoint}
              onUpdateEndpoint={updateEndpoint}
              onRemoveEndpoint={removeEndpoint}
              responseSchema={responseSchema}
              onAddResponseField={addResponseField}
              onUpdateResponseField={updateResponseField}
              onRemoveResponseField={removeResponseField}
              expectedPayload={expectedPayload}
              onExpectedPayloadChange={setExpectedPayload}
              expectedPayloadError={expectedPayloadError}
              parsing={parsing}
              onSpecUpload={handleSpecUpload}
            />
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
