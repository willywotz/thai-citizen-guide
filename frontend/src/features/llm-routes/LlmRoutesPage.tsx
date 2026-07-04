import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/shared/components/ui/button";
import { Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import {
  listRoutes,
  createRoute,
  updateRoute,
  deleteRoute,
  listPurposes,
  type LlmRoute,
  type LlmRouteInput,
} from "@/features/llm-routes/llmRouteApi";
import { listProviders } from "@/features/llm-providers/llmProviderApi";
import { useAuth } from "@/features/auth/useAuth";
import { LlmRoutesList } from "./LlmRoutesList";
import { CreateLlmRouteDialog } from "./CreateLlmRouteDialog";
import { EditLlmRouteDialog } from "./EditLlmRouteDialog";
import { DeleteLlmRouteDialog } from "./DeleteLlmRouteDialog";

const QUERY_KEY = ["llm-routes"];

export default function LlmRoutesPage() {
  const queryClient = useQueryClient();
  const { isReadOnly } = useAuth();

  const { data, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: listRoutes,
  });
  const routes = data?.data ?? [];

  const { data: purposesData, isLoading: purposesLoading } = useQuery({
    queryKey: ["llm-purposes"],
    queryFn: listPurposes,
  });
  const purposes = purposesData?.data ?? [];

  const { data: providersData, isLoading: providersLoading } = useQuery({
    queryKey: ["llm-providers"],
    queryFn: listProviders,
  });
  const providers = providersData?.data ?? [];

  // Create
  const [createOpen, setCreateOpen] = useState(false);
  const createMutation = useMutation({
    mutationFn: (input: LlmRouteInput) => createRoute(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      toast.success("สร้างเส้นทาง LLM เรียบร้อย");
      setCreateOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Edit
  const [editTarget, setEditTarget] = useState<LlmRoute | null>(null);
  const editMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<LlmRouteInput> }) =>
      updateRoute(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      toast.success("แก้ไขเส้นทาง LLM เรียบร้อย");
      setEditTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Delete
  const [deleteTarget, setDeleteTarget] = useState<LlmRoute | null>(null);
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteRoute(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      toast.success("ลบเส้นทาง LLM เรียบร้อย");
      setDeleteTarget(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">เส้นทาง LLM</h2>
        {!isReadOnly && (
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-1" />
            เพิ่มเส้นทาง
          </Button>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      )}

      {!isLoading && (
        <LlmRoutesList
          routes={routes}
          isReadOnly={isReadOnly}
          onEdit={setEditTarget}
          onDelete={setDeleteTarget}
        />
      )}

      <CreateLlmRouteDialog
        open={createOpen}
        purposes={purposes}
        purposesLoading={purposesLoading}
        providers={providers}
        providersLoading={providersLoading}
        mutation={createMutation}
        onClose={() => setCreateOpen(false)}
      />

      <EditLlmRouteDialog
        target={editTarget}
        providers={providers}
        providersLoading={providersLoading}
        mutation={editMutation}
        onClose={() => setEditTarget(null)}
      />

      <DeleteLlmRouteDialog
        target={deleteTarget}
        mutation={deleteMutation}
        onConfirm={() => deleteMutation.mutate(deleteTarget!.id)}
        onClose={() => setDeleteTarget(null)}
      />
    </div>
  );
}
