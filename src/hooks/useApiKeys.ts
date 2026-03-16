import { useState, useEffect, useCallback } from "react";
import { supabase } from "@/integrations/supabase/client";
import type { ApiKey, ApiKeyCreateInput } from "@/types/auth";
import { toast } from "sonner";

async function getAuthHeader(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session ? `Bearer ${session.access_token}` : null;
}

const FUNCTION_URL = `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/manage-api-keys`;

export function useApiKeys() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchKeys = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const authHeader = await getAuthHeader();
    if (!authHeader) { setIsLoading(false); return; }

    try {
      const res = await fetch(FUNCTION_URL, {
        headers: { Authorization: authHeader },
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "Failed to fetch keys");
      setKeys(
        (json.data ?? []).map((k: any) => ({
          id: k.id,
          name: k.name,
          keyPrefix: k.key_prefix,
          scopes: k.scopes ?? [],
          expiresAt: k.expires_at ?? null,
          lastUsedAt: k.last_used_at ?? null,
          revokedAt: k.revoked_at ?? null,
          createdAt: k.created_at,
        }))
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchKeys(); }, [fetchKeys]);

  const createKey = useCallback(async (input: ApiKeyCreateInput): Promise<string | null> => {
    const authHeader = await getAuthHeader();
    if (!authHeader) return null;

    try {
      const res = await fetch(FUNCTION_URL, {
        method: "POST",
        headers: { Authorization: authHeader, "Content-Type": "application/json" },
        body: JSON.stringify({
          name: input.name,
          scopes: input.scopes,
          expires_at: input.expiresAt ?? null,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "Failed to create key");

      await fetchKeys();
      return json.data.raw_key as string;
    } catch (e: any) {
      toast.error(e.message);
      return null;
    }
  }, [fetchKeys]);

  const revokeKey = useCallback(async (keyId: string) => {
    const authHeader = await getAuthHeader();
    if (!authHeader) return;

    try {
      const res = await fetch(`${FUNCTION_URL}?id=${keyId}`, {
        method: "DELETE",
        headers: { Authorization: authHeader },
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "Failed to revoke key");
      toast.success("ยกเลิก API Key แล้ว");
      await fetchKeys();
    } catch (e: any) {
      toast.error(e.message);
    }
  }, [fetchKeys]);

  return { keys, isLoading, error, createKey, revokeKey, refresh: fetchKeys };
}
