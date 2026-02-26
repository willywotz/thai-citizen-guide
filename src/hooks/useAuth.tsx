import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { supabase } from "@/integrations/supabase/client";
import type { User, Session } from "@supabase/supabase-js";

interface AuthContextType {
  user: User | null;
  session: Session | null;
  isAdmin: boolean;
  isLoading: boolean;
  profile: { displayName: string; avatarUrl: string | null } | null;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  session: null,
  isAdmin: false,
  isLoading: true,
  profile: null,
  signOut: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [profile, setProfile] = useState<AuthContextType["profile"]>(null);

  const fetchUserDetails = useCallback(async (userId: string, email?: string) => {
    try {
      const [profileRes, roleRes] = await Promise.all([
        supabase
          .from("profiles")
          .select("display_name, avatar_url")
          .eq("id", userId)
          .single(),
        supabase
          .from("user_roles")
          .select("role")
          .eq("user_id", userId)
          .eq("role", "admin")
          .maybeSingle(),
      ]);

      if (profileRes.data) {
        setProfile({
          displayName: (profileRes.data as any).display_name || email || "",
          avatarUrl: (profileRes.data as any).avatar_url,
        });
      }

      setIsAdmin(!!roleRes.data);
    } catch {
      // Fail silently
    }
  }, []);

  useEffect(() => {
    // Set up listener FIRST
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
        setUser(session?.user ?? null);

        if (session?.user) {
          // Use setTimeout to avoid Supabase deadlock warning
          setTimeout(() => {
            fetchUserDetails(session.user.id, session.user.email ?? undefined).then(() => {
              setIsLoading(false);
            });
          }, 0);
        } else {
          setProfile(null);
          setIsAdmin(false);
          setIsLoading(false);
        }
      }
    );

    // THEN check for existing session
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        setIsLoading(false);
      }
      // If session exists, onAuthStateChange will fire and handle it
    });

    return () => subscription.unsubscribe();
  }, [fetchUserDetails]);

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider value={{ user, session, isAdmin, isLoading, profile, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
