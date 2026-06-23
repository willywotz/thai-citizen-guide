import { useState } from "react";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";
import type { Agency, ApiHeader } from "@/shared/types/agency";

import { parseExpectedPayload } from "../agencyForm";
import { useUpdateAgency } from "../useAgencies";
import { HeadersEditor } from "../wizard/HeadersEditor";

export function ConnectionTab({ agency }: { agency: Agency }) {
  const updateMutation = useUpdateAgency();
  const [endpointUrl, setEndpointUrl] = useState(agency.endpointUrl ?? "");
  const [apiHeaders, setApiHeaders] = useState<ApiHeader[]>(agency.apiHeaders ?? []);
  const [payloadRaw, setPayloadRaw] = useState(
    agency.expectedPayload ? JSON.stringify(agency.expectedPayload, null, 2) : "",
  );
  const [mcpToolName, setMcpToolName] = useState(agency.mcpToolName ?? "");

  const { value: parsedPayload, error: payloadError } = parseExpectedPayload(payloadRaw);
  const urlValid = z.string().url().safeParse(endpointUrl).success;

  const save = async () => {
    try {
      await updateMutation.mutateAsync({
        id: agency.id,
        endpointUrl,
        apiHeaders: apiHeaders.filter((h) => h.name && h.value),
        expectedPayload: parsedPayload,
        mcpToolName: mcpToolName || null,
      });
      toast.success("บันทึกการเชื่อมต่อสำเร็จ");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "เกิดข้อผิดพลาด");
    }
  };

  return (
    <div className="space-y-5 max-w-lg">
      <div className="space-y-1.5">
        <Label htmlFor="conn-endpoint">Endpoint URL</Label>
        <Input id="conn-endpoint" placeholder="https://…" value={endpointUrl} onChange={(e) => setEndpointUrl(e.target.value)} />
      </div>

      {agency.connectionType === "API" && (
        <>
          <div className="space-y-1.5">
            <Label>Headers</Label>
            <HeadersEditor headers={apiHeaders} onChange={setApiHeaders} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="conn-payload">Expected payload (JSON template)</Label>
            <Textarea
              id="conn-payload"
              rows={5}
              placeholder='{"query": "__query__", "session_id": "__session_id__"}'
              value={payloadRaw}
              onChange={(e) => setPayloadRaw(e.target.value)}
              className="font-mono text-xs"
            />
            {payloadError && <p className="text-xs text-destructive">JSON ไม่ถูกต้อง</p>}
          </div>
        </>
      )}

      {agency.connectionType === "MCP" && (
        <div className="space-y-1.5">
          <Label htmlFor="conn-tool">MCP tool</Label>
          <Input id="conn-tool" placeholder="เช่น chat_with_agency" value={mcpToolName} onChange={(e) => setMcpToolName(e.target.value)} className="font-mono" />
        </div>
      )}

      <Button onClick={save} disabled={updateMutation.isPending || payloadError || !urlValid}>
        {updateMutation.isPending ? "กำลังบันทึก…" : "บันทึก"}
      </Button>
    </div>
  );
}
