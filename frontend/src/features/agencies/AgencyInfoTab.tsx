import { Card, CardContent } from "@/shared/components/ui/card";
import { Badge } from "@/shared/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/components/ui/table";
import type { Agency } from "@/shared/types";

interface Props { agency: Agency }

export function AgencyInfoTab({ agency }: Props) {
  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-muted-foreground mb-1">ชื่อย่อ</p>
            <p className="text-sm font-medium text-foreground">{agency.shortName}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">ประเภทการเชื่อมต่อ</p>
            <p className="text-sm font-medium text-foreground">{agency.connectionType}</p>
          </div>
          <div className="md:col-span-2">
            <p className="text-xs text-muted-foreground mb-1">Endpoint URL</p>
            <p className="text-sm font-mono text-foreground break-all">{agency.endpointUrl || "-"}</p>
          </div>

          {agency.connectionType === "API" && (
            <>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Auth Method</p>
                <p className="text-sm font-medium text-foreground">{agency.authMethod || "api_key"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Auth Header</p>
                <p className="text-sm font-mono text-foreground">{agency.authHeader || "-"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Base Path</p>
                <p className="text-sm font-mono text-foreground">{agency.basePath || "-"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Rate Limit</p>
                <p className="text-sm font-medium text-foreground">{agency.rateLimitRpm ? `${agency.rateLimitRpm} RPM` : "-"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Request Format</p>
                <p className="text-sm font-medium text-foreground uppercase">{agency.requestFormat || "json"}</p>
              </div>
              {agency.apiEndpoints && agency.apiEndpoints.length > 0 && (
                <div className="md:col-span-2">
                  <p className="text-xs text-muted-foreground mb-2">API Endpoints ({agency.apiEndpoints.length})</p>
                  <div className="border border-border rounded-md overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[80px] text-xs">Method</TableHead>
                          <TableHead className="text-xs">Path</TableHead>
                          <TableHead className="text-xs">คำอธิบาย</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {agency.apiEndpoints.map((ep, i) => (
                          <TableRow key={i}>
                            <TableCell><Badge variant="outline" className="text-[10px] font-mono">{ep.method}</Badge></TableCell>
                            <TableCell className="text-xs font-mono">{ep.path}</TableCell>
                            <TableCell className="text-xs text-muted-foreground">{ep.description}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
              {agency.responseSchema && agency.responseSchema.length > 0 && (
                <div className="md:col-span-2">
                  <p className="text-xs text-muted-foreground mb-2">Response Schema ({agency.responseSchema.length} fields)</p>
                  <div className="border border-border rounded-md overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs">Field</TableHead>
                          <TableHead className="w-[80px] text-xs">Type</TableHead>
                          <TableHead className="text-xs">คำอธิบาย</TableHead>
                          <TableHead className="text-xs">ตัวอย่าง</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {agency.responseSchema.map((f, i) => (
                          <TableRow key={i}>
                            <TableCell className="text-xs font-mono text-foreground">{f.field}</TableCell>
                            <TableCell><Badge variant="outline" className="text-[10px] font-mono">{f.type}</Badge></TableCell>
                            <TableCell className="text-xs text-muted-foreground">{f.description}</TableCell>
                            <TableCell className="text-xs font-mono text-muted-foreground">{f.example || "-"}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
            </>
          )}

          <div className="md:col-span-2">
            <p className="text-xs text-muted-foreground mb-1.5">ขอบเขตข้อมูล</p>
            <div className="flex flex-wrap gap-1.5">
              {agency.dataScope.map((scope, i) => (
                <span key={i} className="text-[11px] bg-accent text-accent-foreground px-2.5 py-1 rounded-full">
                  {scope}
                </span>
              ))}
            </div>
          </div>
          {agency.apiKeyName && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">API Key Name</p>
              <p className="text-sm font-mono text-foreground">{agency.apiKeyName}</p>
            </div>
          )}
          {agency.expectedPayload && (
            <div className="md:col-span-2">
              <p className="text-xs text-muted-foreground mb-1.5">Expected Payload</p>
              <pre className="text-xs font-mono bg-muted rounded-md p-3 overflow-x-auto border border-border whitespace-pre-wrap break-all">
                {JSON.stringify(agency.expectedPayload, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
