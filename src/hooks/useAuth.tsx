import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { supabase } from "@/integrations/supabase/client";
import type { User, Session } from "@supabase/supabase-js";
import type { AuthContextType, AppRole, AppPermission, UserProfile } from "@/types/auth";

const AuthContext = createContext<AuthContextType>({
  user: null,
  session: null,
  profile: null,
  roles: [],
  permissions: [],
  isLoading: true,
  isSuperAdmin: false,
  isAdmin: false,
  isModerator: false,
  isEmailVerified: false,
  signOut: async () => {},
  hasRole: () => false,
  hasPermission: () => false,
  refreshProfile: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [roles, setRoles] = useState<AppRole[]>([]);
  const [permissions, setPermissions] = useState<AppPermission[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUserDetails = useCallback(async (userId: string, currentSession: Session | null) => {
    try {
      // Prefer roles from JWT claims (no extra DB call if hook is enabled)
      const jwtRoles: AppRole[] =
        (currentSession?.access_token
          ? (JSON.parse(atob(currentSession.access_token.split('.')[1])) as any)?.user_roles ?? []
          : []
        ).filter(Boolean);

      // Fall back to DB query if JWT has no roles embedded yet
      let resolvedRoles: AppRole[] = jwtRoles;
      if (resolvedRoles.length === 0) {
        const { data: roleRows } = await supabase
          .from("user_roles")
          .select("role")
          .eq("user_id", userId);
        resolvedRoles = (roleRows ?? []).map((r: any) => r.role as AppRole);
      }

      // Fetch profile
      const { data: profileRow } = await supabase
        .from("profiles")
        .select("display_name, avatar_url, email_verified, email_verified_at, auth_provider, is_active, created_at, updated_at")
        .eq("id", userId)
        .single();

      // Fetch permissions for the user's roles
      let resolvedPermissions: AppPermission[] = [];
      if (resolvedRoles.length > 0) {
        const { data: permRows } = await supabase
          .from("role_permissions")
          .select("permission")
          .in("role", resolvedRoles);
        const unique = new Set((permRows ?? []).map((p: any) => p.permission as AppPermission));
        resolvedPermissions = Array.from(unique);
      }

      setRoles(resolvedRoles);
      setPermissions(resolvedPermissions);

      if (profileRow) {
        setProfile({
          id: userId,
          displayName: (profileRow as any).display_name || currentSession?.user?.email?.split("@")[0] || "",
          avatarUrl: (profileRow as any).avatar_url ?? null,
          email: currentSession?.user?.email ?? null,
          emailVerified: (profileRow as any).email_verified ?? false,
          emailVerifiedAt: (profileRow as any).email_verified_at ?? null,
          authProvider: (profileRow as any).auth_provider ?? "email",
          isActive: (profileRow as any).is_active ?? true,
          createdAt: (profileRow as any).created_at ?? "",
          updatedAt: (profileRow as any).updated_at ?? "",
        });
      }
    } catch {
      // Fail silently
    }
  }, []);

  const refreshProfile = useCallback(async () => {
    if (!user || !session) return;
    await fetchUserDetails(user.id, session);
  }, [user, session, fetchUserDetails]);

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, newSession) => {
        setSession(newSession);
        setUser(newSession?.user ?? null);

        if (newSession?.user) {
          setTimeout(() => {
            fetchUserDetails(newSession.user.id, newSession).then(() => setIsLoading(false));
          }, 0);
        } else {
          setProfile(null);
          setRoles([]);
          setPermissions([]);
          setIsLoading(false);
        }
      }
    );

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) setIsLoading(false);
    });

    return () => subscription.unsubscribe();
  }, [fetchUserDetails]);

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  const hasRole = useCallback((role: AppRole) => roles.includes(role), [roles]);
  const hasPermission = useCallback((permission: AppPermission) => permissions.includes(permission), [permissions]);

  const isSuperAdmin = roles.includes("super_admin");
  const isAdmin = isSuperAdmin || roles.includes("admin");
  const isModerator = isAdmin || roles.includes("moderator");
  const isEmailVerified = profile?.emailVerified ?? false;

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        profile,
        roles,
        permissions,
        isLoading,
        isSuperAdmin,
        isAdmin,
        isModerator,
        isEmailVerified,
        signOut,
        hasRole,
        hasPermission,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
