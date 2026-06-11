import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/components/ui/select";
import { Plus, Upload, Loader2, Trash2 } from "lucide-react";
import type { ApiEndpoint, ResponseField } from "@/shared/types/agency";

interface Props {
  // Auth / config
  authMethod: string;
  onAuthMethodChange: (v: string) => void;
  authHeader: string;
  onAuthHeaderChange: (v: string) => void;
  basePath: string;
  onBasePathChange: (v: string) => void;
  rateLimitRpm: string;
  onRateLimitRpmChange: (v: string) => void;
  requestFormat: string;
  onRequestFormatChange: (v: string) => void;
  // Endpoints
  apiEndpoints: ApiEndpoint[];
  onAddEndpoint: () => void;
  onUpdateEndpoint: (index: number, field: keyof ApiEndpoint, value: string) => void;
  onRemoveEndpoint: (index: number) => void;
  // Response schema
  responseSchema: ResponseField[];
  onAddResponseField: () => void;
  onUpdateResponseField: (index: number, field: keyof ResponseField, value: string) => void;
  onRemoveResponseField: (index: number) => void;
  // Expected payload
  expectedPayload: string;
  onExpectedPayloadChange: (v: string) => void;
  expectedPayloadError: boolean;
  // Spec upload
  parsing: boolean;
  onSpecUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

export function AgencyApiFields({
  authMethod, onAuthMethodChange,
  authHeader, onAuthHeaderChange,
  basePath, onBasePathChange,
  rateLimitRpm, onRateLimitRpmChange,
  requestFormat, onRequestFormatChange,
  apiEndpoints, onAddEndpoint, onUpdateEndpoint, onRemoveEndpoint,
  responseSchema, onAddResponseField, onUpdateResponseField, onRemoveResponseField,
  expectedPayload, onExpectedPayloadChange, expectedPayloadError,
  parsing, onSpecUpload,
}: Props) {
  return (
    <div className="space-y-4 border border-border rounded-lg p-4 bg-muted/30">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-foreground">⚙️ API Configuration</p>
        <label className="cursor-pointer">
          <input
            type="file"
            accept=".json,.yaml,.yml"
            className="hidden"
            onChange={onSpecUpload}
            disabled={parsing}
          />
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
          <Select value={authMethod} onValueChange={onAuthMethodChange}>
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
          <Input
            value={authHeader}
            onChange={(e) => onAuthHeaderChange(e.target.value)}
            placeholder="X-API-Key"
            className="h-9"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label className="text-xs">Base Path</Label>
          <Input
            value={basePath}
            onChange={(e) => onBasePathChange(e.target.value)}
            placeholder="/api/v1"
            className="h-9"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Rate Limit (RPM)</Label>
          <Input
            type="number"
            value={rateLimitRpm}
            onChange={(e) => onRateLimitRpmChange(e.target.value)}
            placeholder="60"
            className="h-9"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs">Request Format</Label>
        <Select value={requestFormat} onValueChange={onRequestFormatChange}>
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
          <Button type="button" variant="ghost" size="sm" className="h-7 text-xs gap-1" onClick={onAddEndpoint}>
            <Plus className="h-3 w-3" /> เพิ่ม
          </Button>
        </div>
        {apiEndpoints.map((ep, i) => (
          <div key={i} className="flex gap-2 items-start">
            <Select value={ep.method} onValueChange={(v) => onUpdateEndpoint(i, "method", v)}>
              <SelectTrigger className="h-8 w-[90px] text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                {["GET", "POST", "PUT", "DELETE", "PATCH"].map((m) => (
                  <SelectItem key={m} value={m}>{m}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              value={ep.path}
              onChange={(e) => onUpdateEndpoint(i, "path", e.target.value)}
              placeholder="/path"
              className="h-8 text-xs flex-1"
            />
            <Input
              value={ep.description}
              onChange={(e) => onUpdateEndpoint(i, "description", e.target.value)}
              placeholder="คำอธิบาย"
              className="h-8 text-xs flex-1"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={() => onRemoveEndpoint(i)}
            >
              <Trash2 className="h-3.5 w-3.5 text-destructive" />
            </Button>
          </div>
        ))}
        {apiEndpoints.length === 0 && (
          <p className="text-[11px] text-muted-foreground text-center py-2">
            ยังไม่มี endpoint — กดเพิ่ม หรือ Upload API Spec
          </p>
        )}
      </div>

      {/* Response Schema */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-xs">Response Schema (LLM Parse Guide)</Label>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 text-xs gap-1"
            onClick={onAddResponseField}
          >
            <Plus className="h-3 w-3" /> เพิ่ม
          </Button>
        </div>
        {responseSchema.map((f, i) => (
          <div key={i} className="flex gap-2 items-start">
            <Input
              value={f.field}
              onChange={(e) => onUpdateResponseField(i, "field", e.target.value)}
              placeholder="field.path"
              className="h-8 text-xs flex-1"
            />
            <Select value={f.type} onValueChange={(v) => onUpdateResponseField(i, "type", v)}>
              <SelectTrigger className="h-8 w-[90px] text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                {["string", "number", "boolean", "array", "object", "date"].map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              value={f.description}
              onChange={(e) => onUpdateResponseField(i, "description", e.target.value)}
              placeholder="คำอธิบาย"
              className="h-8 text-xs flex-1"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={() => onRemoveResponseField(i)}
            >
              <Trash2 className="h-3.5 w-3.5 text-destructive" />
            </Button>
          </div>
        ))}
        {responseSchema.length === 0 && (
          <p className="text-[11px] text-muted-foreground text-center py-2">
            ยังไม่มี schema — กดเพิ่ม หรือ Upload API Spec เพื่อสร้างอัตโนมัติ
          </p>
        )}
      </div>

      {/* Expected Payload */}
      <div className="space-y-1.5">
        <Label className="text-xs">Expected Payload (JSON)</Label>
        <Textarea
          value={expectedPayload}
          onChange={(e) => onExpectedPayloadChange(e.target.value)}
          placeholder={'{\n  "query": "string",\n  "limit": 10\n}'}
          rows={5}
          className={`font-mono text-xs resize-y ${expectedPayloadError ? "border-destructive" : ""}`}
        />
        {expectedPayloadError && (
          <p className="text-[11px] text-destructive">JSON ไม่ถูกต้อง</p>
        )}
        <p className="text-[11px] text-muted-foreground">
          โครงสร้าง request body ที่ LLM ควรส่งให้ API นี้
        </p>
      </div>
    </div>
  );
}
