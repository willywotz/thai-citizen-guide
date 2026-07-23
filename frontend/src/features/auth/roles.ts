export type Role = "user" | "admin";

const ALL: Role[] = ["user", "admin"];
const ADMIN: Role[] = ["admin"];

/**
 * Roles permitted to view each route. Single source of truth shared by the
 * route guard (ProtectedRoute) and the sidebar. Keep in sync with the backend
 * allowlist in backend/app/auth/dependencies.py.
 */
export const ROUTE_ROLES: Record<string, Role[]> = {
  "/chat": ALL,
  "/architecture": ALL,
  "/dashboard": ALL,
  "/executive": ALL,
  "/health": ALL,
  "/heatmap": ALL,
  "/usage": ALL,
  "/feedback": ALL,
  "/agencies": ADMIN,
  "/agencies/:id": ADMIN,
  "/history": ALL,
  "/connection-logs": ADMIN,
  "/api-keys": ADMIN,
  "/agencies/new": ADMIN,
  "/agencies/:id/setup": ADMIN,
  "/users": ADMIN,
  "/audit-log": ADMIN,
  "/settings": ALL,
  "/settings/system": ADMIN,
  "/settings/llm": ADMIN,
  "/settings/api-keys": ADMIN,
  "/settings/usage": ALL,
  "/settings/connections": ADMIN,
  "/settings/audit": ADMIN,
  "/llm-settings": ADMIN,
  "/popular-questions": ADMIN,
};

export function canAccess(role: Role, path: string): boolean {
  const allowed = ROUTE_ROLES[path];
  return allowed ? allowed.includes(role) : true;
}
