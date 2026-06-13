import { Navigate } from "react-router-dom";
import { useAuth } from "@/features/auth/useAuth";
import { Skeleton } from "@/shared/components/ui/skeleton";
import type { Role } from "@/features/auth/roles";

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
  allowedRoles?: Role[];
}

export function ProtectedRoute({ children, requireAdmin = false, allowedRoles }: ProtectedRouteProps) {
  const { user, isAdmin, isLoading } = useAuth();

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

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // A role not permitted for this route is sent to /chat (reachable by every authenticated role).
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/chat" replace />;
  }

  if (requireAdmin && !isAdmin) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center space-y-2">
          <p className="text-lg font-semibold text-foreground">ไม่มีสิทธิ์เข้าถึง</p>
          <p className="text-sm text-muted-foreground">คุณต้องมีสิทธิ์ admin เพื่อเข้าถึงหน้านี้</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
