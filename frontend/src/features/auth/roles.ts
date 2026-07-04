export type Role = "user" | "viewer" | "auditor" | "agency_owner" | "admin";

const ALL: Role[] = ["user", "viewer", "auditor", "agency_owner", "admin"];

/**
 * Roles permitted to view each route. Single source of truth shared by the
 * route guard (ProtectedRoute) and the sidebar. Keep in sync with the backend
 * allowlist in backend/app/auth/dependencies.py.
 */
export const ROUTE_ROLES: Record<string, Role[]> = {
  "/chat": ALL,
  "/architecture": ALL,
  "/dashboard": ["viewer", "auditor", "agency_owner", "admin"],
  "/executive": ["viewer", "auditor", "agency_owner", "admin"],
  "/health": ["viewer", "auditor", "agency_owner", "admin"],
  "/heatmap": ["viewer", "auditor", "agency_owner", "admin"],
  "/usage": ["viewer", "auditor", "admin"],
  "/feedback": ["viewer", "auditor", "admin"],
  "/agencies": ["auditor", "agency_owner", "admin"],
  "/agencies/:id": ["auditor", "agency_owner", "admin"],
  "/history": ["auditor", "agency_owner", "admin"],
  "/connection-logs": ["auditor", "agency_owner", "admin"],
  "/api-keys": ["auditor", "agency_owner", "admin"],
  "/my-agencies": ["agency_owner", "admin"],
  "/agencies/new": ["agency_owner", "admin"],
  "/agencies/:id/setup": ["agency_owner", "admin"],
  "/users": ["auditor", "admin"],
  "/audit-log": ["auditor", "admin"],
  "/settings": ["admin"],
  "/llm-providers": ["admin"],
  "/llm-routes": ["admin"],
};

export const READ_ONLY_ROLES: Role[] = ["viewer", "auditor"];

export function canAccess(role: Role, path: string): boolean {
  const allowed = ROUTE_ROLES[path];
  return allowed ? allowed.includes(role) : true;
}

export function isReadOnlyRole(role: Role | undefined): boolean {
  return role !== undefined && READ_ONLY_ROLES.includes(role);
}
