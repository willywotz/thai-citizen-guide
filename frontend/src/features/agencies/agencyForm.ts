import type { Agency, ApiEndpoint, ResponseField, ApiHeader } from "@/shared/types/agency";

// ---------------------------------------------------------------------------
// Form state shape
// ---------------------------------------------------------------------------

export interface AgencyFormState {
  name: string;
  shortName: string;
  logo: string;
  description: string;
  connectionType: "MCP" | "API" | "A2A";
  endpointUrl: string;
  color: string;
  scopeInput: string;
  dataScope: string[];
  status: "active" | "inactive";
  // API-specific
  authMethod: string;
  authHeader: string;
  basePath: string;
  rateLimitRpm: string;
  requestFormat: string;
  apiEndpoints: ApiEndpoint[];
  responseSchema: ResponseField[];
  expectedPayload: string;
  apiSpecRaw: string;
  apiHeaders: ApiHeader[];
}

// ---------------------------------------------------------------------------
// Parse-spec API response types
// ---------------------------------------------------------------------------

export interface ParsedSpec {
  auth_method?: string;
  auth_header?: string;
  base_path?: string;
  rate_limit_rpm?: number;
  request_format?: string;
  endpoints?: ApiEndpoint[];
  response_schema?: ResponseField[];
  expected_payload?: Record<string, unknown>;
}

export interface ParseSpecResponse {
  success: boolean;
  data?: ParsedSpec;
}

// ---------------------------------------------------------------------------
// Default form state
// ---------------------------------------------------------------------------

export const DEFAULT_FORM_STATE: AgencyFormState = {
  name: "",
  shortName: "",
  logo: "🏢",
  description: "",
  connectionType: "API",
  endpointUrl: "",
  color: "hsl(213 70% 45%)",
  scopeInput: "",
  dataScope: [],
  status: "active",
  authMethod: "api_key",
  authHeader: "",
  basePath: "",
  rateLimitRpm: "",
  requestFormat: "json",
  apiEndpoints: [],
  responseSchema: [],
  expectedPayload: "",
  apiSpecRaw: "",
  apiHeaders: [],
};

// ---------------------------------------------------------------------------
// Build form defaults from an existing Agency
// ---------------------------------------------------------------------------

export function agencyToFormState(agency: Agency): AgencyFormState {
  return {
    name: agency.name,
    shortName: agency.shortName,
    logo: agency.logo,
    description: agency.description,
    connectionType: agency.connectionType,
    endpointUrl: agency.endpointUrl ?? "",
    color: agency.color,
    scopeInput: "",
    dataScope: agency.dataScope,
    status: agency.status,
    authMethod: agency.authMethod ?? "api_key",
    authHeader: agency.authHeader ?? "",
    basePath: agency.basePath ?? "",
    rateLimitRpm: agency.rateLimitRpm != null ? String(agency.rateLimitRpm) : "",
    requestFormat: agency.requestFormat ?? "json",
    apiEndpoints: agency.apiEndpoints ?? [],
    responseSchema: agency.responseSchema ?? [],
    expectedPayload: agency.expectedPayload
      ? JSON.stringify(agency.expectedPayload, null, 2)
      : "",
    apiSpecRaw: agency.apiSpecRaw ?? "",
    apiHeaders: agency.apiHeaders ?? [],
  };
}

// ---------------------------------------------------------------------------
// Validate form (returns true if valid)
// ---------------------------------------------------------------------------

export function isFormValid(state: Pick<AgencyFormState, "name" | "shortName">): boolean {
  return Boolean(state.name.trim() && state.shortName.trim());
}

// ---------------------------------------------------------------------------
// Build partial Agency payload for onSave
// ---------------------------------------------------------------------------

export function buildSavePayload(
  state: AgencyFormState,
  parsedPayload: Record<string, unknown> | null,
): Partial<Agency> {
  const base: Partial<Agency> = {
    name: state.name,
    shortName: state.shortName,
    logo: state.logo,
    description: state.description,
    connectionType: state.connectionType,
    endpointUrl: state.endpointUrl,
    color: state.color,
    dataScope: state.dataScope,
    status: state.status,
  };

  if (state.connectionType === "API") {
    return {
      ...base,
      authMethod: state.authMethod,
      authHeader: state.authHeader,
      basePath: state.basePath,
      rateLimitRpm: (() => { const rpm = state.rateLimitRpm ? parseInt(state.rateLimitRpm, 10) : null; return rpm !== null && !Number.isNaN(rpm) ? rpm : null; })(),
      requestFormat: state.requestFormat,
      apiEndpoints: state.apiEndpoints.filter((ep) => ep.path),
      responseSchema: state.responseSchema.filter((f) => f.field),
      expectedPayload: parsedPayload,
      apiSpecRaw: state.apiSpecRaw,
      apiHeaders: state.apiHeaders.filter((h) => h.name && h.value),
    };
  }

  return base;
}

// ---------------------------------------------------------------------------
// Parse expectedPayload JSON string → object or null
// ---------------------------------------------------------------------------

export function parseExpectedPayload(raw: string): {
  value: Record<string, unknown> | null;
  error: boolean;
} {
  const trimmed = raw.trim();
  if (!trimmed) return { value: null, error: false };
  try {
    return { value: JSON.parse(trimmed) as Record<string, unknown>, error: false };
  } catch {
    return { value: null, error: true };
  }
}

// ---------------------------------------------------------------------------
// Protocol info labels
// ---------------------------------------------------------------------------

export const PROTOCOL_INFO: Record<string, string> = {
  MCP: "Model Context Protocol — มาตรฐานการเชื่อมต่อ AI กับเครื่องมือภายนอก รองรับ tools/list, tools/call, resources/read",
  A2A: "Agent-to-Agent Protocol — มาตรฐานการสื่อสารระหว่าง AI Agent ผ่าน Agent Card exchange",
  API: "REST API — การเชื่อมต่อผ่าน HTTP endpoint มาตรฐาน พร้อม authentication",
};
