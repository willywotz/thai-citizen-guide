import { useState, useEffect, useCallback } from "react";
import { supabase } from "@/integrations/supabase/client";
import type { AdminUserView, AppRole } from "@/types/auth";
import { toast } from "sonner";

const FUNCTION_URL = `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/manage-users`;

async function getAuthHeader(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session ? `Bearer ${session.access_token}` : null;
}

export function useUserManagement() {
  const [users, setUsers] = useState<AdminUserView[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState("");

  const fetchUsers = useCallback(async (searchQuery = "") => {
    setIsLoading(true);
    const authHeader = await getAuthHeader();
    if (!authHeader) { setIsLoading(false); return; }

    try {
      const params = new URLSearchParams();
      if (searchQuery) params.set("search", searchQuery);
      const res = await fetch(`${FUNCTION_URL}?${params}`, {
        headers: { Authorization: authHeader },
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "Failed to fetch users");
      setUsers(json.data ?? []);
      setTotal(json.total ?? 0);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(search); }, [fetchUsers, search]);

  const assignRole = useCallback(async (userId: string, role: AppRole) => {
    const authHeader = await getAuthHeader();
    if (!authHeader) return;
    const res = await fetch(FUNCTION_URL, {
      method: "PUT",
      headers: { Authorization: authHeader, "Content-Type": "application/json" },
      body: JSON.stringify({ action: "assign_role", user_id: userId, role }),
    });
    const json = await res.json();
    if (!res.ok) { toast.error(json.error ?? "Failed"); return; }
    toast.success("กำหนดสิทธิ์แล้ว");
    await fetchUsers(search);
  }, [fetchUsers, search]);

  const removeRole = useCallback(async (userId: string, role: AppRole) => {
    const authHeader = await getAuthHeader();
    if (!authHeader) return;
    const res = await fetch(FUNCTION_URL, {
      method: "PUT",
      headers: { Authorization: authHeader, "Content-Type": "application/json" },
      body: JSON.stringify({ action: "remove_role", user_id: userId, role }),
    });
    const json = await res.json();
    if (!res.ok) { toast.error(json.error ?? "Failed"); return; }
    toast.success("ลบสิทธิ์แล้ว");
    await fetchUsers(search);
  }, [fetchUsers, search]);

  const toggleActive = useCallback(async (userId: string, isActive: boolean) => {
    const authHeader = await getAuthHeader();
    if (!authHeader) return;
    const res = await fetch(FUNCTION_URL, {
      method: "PUT",
      headers: { Authorization: authHeader, "Content-Type": "application/json" },
      body: JSON.stringify({ action: isActive ? "deactivate" : "activate", user_id: userId }),
    });
    const json = await res.json();
    if (!res.ok) { toast.error(json.error ?? "Failed"); return; }
    toast.success(isActive ? "ระงับบัญชีแล้ว" : "เปิดใช้งานบัญชีแล้ว");
    await fetchUsers(search);
  }, [fetchUsers, search]);

  return { users, total, isLoading, search, setSearch, assignRole, removeRole, toggleActive, refresh: fetchUsers };
}
