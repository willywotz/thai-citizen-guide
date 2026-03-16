import { Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { Skeleton } from "@/components/ui/skeleton";
import type { AppRole, AppPermission } from "@/types/auth";

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
  requireRole?: AppRole;
  requirePermission?: AppPermission;
  requireEmailVerified?: boolean;
}

export function ProtectedRoute({
  children,
  requireAdmin = false,
  requireRole,
  requirePermission,
  requireEmailVerified = false,
}: ProtectedRouteProps) {
  const { user, isAdmin, isLoading, hasRole, hasPermission, isEmailVerified } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="space-y-4 w-64">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  if (requireEmailVerified && !isEmailVerified) {
    return <Navigate to="/verify-email" replace />;
  }

  if (requireAdmin && !isAdmin) {
    return <Forbidden message="คุณต้องมีสิทธิ์ admin เพื่อเข้าถึงหน้านี้" />;
  }

  if (requireRole && !hasRole(requireRole)) {
    return <Forbidden message={`คุณต้องมีสิทธิ์ ${requireRole} เพื่อเข้าถึงหน้านี้`} />;
  }

  if (requirePermission && !hasPermission(requirePermission)) {
    return <Forbidden message="คุณไม่มีสิทธิ์เข้าถึงส่วนนี้" />;
  }

  return <>{children}</>;
}

function Forbidden({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center space-y-2">
        <p className="text-lg font-semibold text-foreground">ไม่มีสิทธิ์เข้าถึง</p>
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}
