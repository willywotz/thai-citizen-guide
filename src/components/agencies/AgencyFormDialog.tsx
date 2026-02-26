import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";
import type { Agency } from "@/types";

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
    } else {
      setName(""); setShortName(""); setLogo("🏢"); setDescription("");
      setConnectionType("API"); setEndpointUrl(""); setColor("hsl(213 70% 45%)");
      setDataScope([]); setStatus("active");
    }
  }, [agency, open]);

  const addScope = () => {
    const v = scopeInput.trim();
    if (v && !dataScope.includes(v)) {
      setDataScope([...dataScope, v]);
      setScopeInput("");
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !shortName) return;
    onSave({ name, shortName, logo, description, connectionType, endpointUrl, color, dataScope, status });
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
