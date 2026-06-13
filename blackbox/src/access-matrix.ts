export type Role = "user" | "viewer" | "auditor" | "agency_owner" | "admin";

export const ROLES: Role[] = ["user", "viewer", "auditor", "agency_owner", "admin"];

export type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface EndpointAccess {
  page: string;
  method: Method;
  path: string;
  roles: Role[];
  body?: unknown;
}

export interface PageAccess {
  path: string;
  roles: Role[];
}

export const ROLE_ACCOUNTS: Record<Role, { email: string }> = {
  user: { email: "bb-user@example.com" },
  viewer: { email: "bb-viewer@example.com" },
  auditor: { email: "bb-auditor@example.com" },
  agency_owner: { email: "bb-agency-owner@example.com" },
  admin: { email: "bb-admin@example.com" },
};

const ANALYTICS: Role[] = ["viewer", "auditor", "agency_owner", "admin"];
const USAGE_FEEDBACK: Role[] = ["viewer", "auditor", "admin"];
const MANAGEMENT: Role[] = ["auditor", "agency_owner", "admin"];
const OWNER: Role[] = ["agency_owner", "admin"];
const AUDIT: Role[] = ["auditor", "admin"];

// Directly-callable load-time reads each role is entitled to.
// {id}-bearing detail endpoints are handled in agencies.test.ts.
export const ENDPOINT_MATRIX: EndpointAccess[] = [
  { page: "/architecture", method: "GET", path: "/api/v1/agencies", roles: ROLES },

  { page: "/dashboard", method: "GET", path: "/api/v1/dashboard/stats", roles: ANALYTICS },
  { page: "/dashboard", method: "GET", path: "/api/v1/insight/usage?group_by=model", roles: ANALYTICS },
  { page: "/dashboard", method: "GET", path: "/api/v1/feedback/stats", roles: ANALYTICS },
  { page: "/executive", method: "GET", path: "/api/v1/executive-summary", roles: ANALYTICS },
  { page: "/health", method: "GET", path: "/api/v1/agency-health", roles: ANALYTICS },
  { page: "/heatmap", method: "GET", path: "/api/v1/usage-heatmap?range=7d", roles: ANALYTICS },

  { page: "/usage", method: "GET", path: "/api/v1/insight/usage?group_by=api_key", roles: USAGE_FEEDBACK },
  { page: "/feedback", method: "GET", path: "/api/v1/feedback/stats", roles: USAGE_FEEDBACK },

  { page: "/history", method: "GET", path: "/api/v1/conversations", roles: MANAGEMENT },
  { page: "/connection-logs", method: "GET", path: "/api/v1/connection-logs", roles: MANAGEMENT },
  { page: "/connection-logs", method: "GET", path: "/api/v1/connection-logs/info", roles: MANAGEMENT },
  { page: "/api-keys", method: "GET", path: "/api/v1/api-keys/", roles: MANAGEMENT },

  { page: "/my-agencies", method: "GET", path: "/api/v1/agencies/mine", roles: OWNER },

  { page: "/users", method: "GET", path: "/api/v1/users", roles: AUDIT },
  { page: "/audit-log", method: "GET", path: "/api/v1/audit-log/", roles: AUDIT },

  { page: "/settings", method: "GET", path: "/api/v1/settings", roles: ["admin"] },
];

// Route → roles allowed to view (from frontend/src/features/auth/roles.ts).
export const PAGE_MATRIX: PageAccess[] = [
  { path: "/chat", roles: ROLES },
  { path: "/architecture", roles: ROLES },
  { path: "/dashboard", roles: ANALYTICS },
  { path: "/executive", roles: ANALYTICS },
  { path: "/health", roles: ANALYTICS },
  { path: "/heatmap", roles: ANALYTICS },
  { path: "/usage", roles: USAGE_FEEDBACK },
  { path: "/feedback", roles: USAGE_FEEDBACK },
  { path: "/agencies", roles: MANAGEMENT },
  { path: "/history", roles: MANAGEMENT },
  { path: "/connection-logs", roles: MANAGEMENT },
  { path: "/api-keys", roles: MANAGEMENT },
  { path: "/my-agencies", roles: OWNER },
  { path: "/users", roles: AUDIT },
  { path: "/audit-log", roles: AUDIT },
  { path: "/settings", roles: ["admin"] },
];
