import type { ReactNode } from "react";
import { AlertCircle } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";

interface QueryStateBoundaryProps {
  isLoading: boolean;
  isError: boolean;
  hasData: boolean;
  onRetry?: () => void;
  loading?: ReactNode;
  children: ReactNode;
}

export function QueryStateBoundary({
  isLoading,
  isError,
  hasData,
  onRetry,
  loading,
  children,
}: QueryStateBoundaryProps) {
  if (isLoading) {
    return loading ? (
      <>{loading}</>
    ) : (
      <div className="p-6 space-y-4">
        <Skeleton className="h-12 w-96" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  if (isError || !hasData) {
    return (
      <div className="p-6">
        <Card className="border-destructive/50">
          <CardContent className="p-8 text-center space-y-3">
            <AlertCircle className="h-10 w-10 mx-auto text-destructive" />
            <p className="font-semibold">ไม่สามารถโหลดข้อมูลได้</p>
            {onRetry && (
              <Button onClick={onRetry} variant="outline">
                ลองอีกครั้ง
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}
