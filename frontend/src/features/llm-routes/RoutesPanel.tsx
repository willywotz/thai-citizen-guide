import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { EditLlmRouteDialog } from "./EditLlmRouteDialog";
import { LlmRoutesList } from "./LlmRoutesList";
import { listRoutes, updateRoute, type LlmRoute, type LlmRouteInput } from "./llmRouteApi";
import { listProviders } from "@/features/llm-providers/llmProviderApi";

const QUERY_KEY = ["llm-routes"];

export function RoutesPanel() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({ queryKey: QUERY_KEY, queryFn: listRoutes });
  const routes = data?.data ?? [];

  const { data: providersData, isLoading: providersLoading } = useQuery({
    queryKey: ["llm-providers"],
    queryFn: listProviders,
  });
  const providers = providersData?.data ?? [];

  const [editTarget, setEditTarget] = useState<LlmRoute | null>(null);
  const editMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<LlmRouteInput> }) => updateRoute(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      toast.success("แก้ไขเส้นทาง LLM เรียบร้อย");
      setEditTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">เส้นทาง LLM</h2>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      )}

      {!isLoading && <LlmRoutesList routes={routes} onEdit={setEditTarget} />}

      <EditLlmRouteDialog
        target={editTarget}
        providers={providers}
        providersLoading={providersLoading}
        mutation={editMutation}
        onClose={() => setEditTarget(null)}
      />
    </div>
  );
}
