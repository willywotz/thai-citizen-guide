import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { api, setToken, clearToken } from "@/lib/apiClient";

interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  is_admin: boolean;
}

interface AuthContextType {
  user: AuthUser | null;
  isAdmin: boolean;
  isLoading: boolean;
  profile: { displayName: string; avatarUrl: string | null } | null;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isAdmin: false,
  isLoading: true,
  profile: null,
  signOut: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setIsLoading(false);
      return;
    }
    try {
      const data = await api.get<AuthUser>("/api/auth/me");
      setUser(data);
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const signOut = async () => {
    clearToken();
    setUser(null);
  };

  const profile = user
    ? { displayName: user.display_name || user.email, avatarUrl: user.avatar_url }
    : null;

  return (
    <AuthContext.Provider value={{ user, isAdmin: user?.is_admin ?? false, isLoading, profile, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function handleAuthResponse(
  data: { access_token: string; user: AuthUser }
) {
  setToken(data.access_token);
}
