export type Role = "user" | "staff" | "admin";

const ALL: Role[] = ["user", "staff", "admin"];
const STAFF: Role[] = ["staff", "admin"];
const ADMIN: Role[] = ["admin"];

/**
 * Roles permitted to view each route. Single source of truth shared by the
 * route guard (ProtectedRoute) and the sidebar. Keep in sync with the backend
 * allowlist in backend/app/auth/dependencies.py.
 */
export const ROUTE_ROLES: Record<string, Role[]> = {
  "/chat": ALL,
  "/architecture": ALL,
  "/history": ALL,
  "/dashboard": STAFF,
  "/executive": STAFF,
  "/health": STAFF,
  "/heatmap": STAFF,
  "/usage": STAFF,
  "/feedback": STAFF,
  "/agencies": ADMIN,
  "/agencies/:id": ADMIN,
  "/agencies/new": ADMIN,
  "/agencies/:id/setup": ADMIN,
  "/connection-logs": ADMIN,
  "/api-keys": ADMIN,
  "/users": ADMIN,
  "/audit-log": ADMIN,
  "/settings": STAFF,
  "/settings/system": ADMIN,
  "/settings/llm": ADMIN,
  "/settings/api-keys": ADMIN,
  "/settings/users": ADMIN,
  "/settings/usage": STAFF,
  "/settings/connections": ADMIN,
  "/settings/audit": ADMIN,
  "/llm-settings": ADMIN,
  "/popular-questions": ADMIN,
};

export function canAccess(role: Role, path: string): boolean {
  const allowed = ROUTE_ROLES[path];
  return allowed ? allowed.includes(role) : true;
}
