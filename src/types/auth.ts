import type { User, Session } from '@supabase/supabase-js';

export type AppRole = 'super_admin' | 'admin' | 'moderator' | 'user' | 'api_user';

export type AppPermission =
  | 'conversations.read.own'
  | 'conversations.read.all'
  | 'conversations.write.own'
  | 'conversations.write.all'
  | 'conversations.delete.own'
  | 'conversations.delete.all'
  | 'agencies.read'
  | 'agencies.write'
  | 'agencies.delete'
  | 'users.read'
  | 'users.write'
  | 'users.delete'
  | 'users.roles.assign'
  | 'api_keys.read.own'
  | 'api_keys.read.all'
  | 'api_keys.write.own'
  | 'api_keys.write.all'
  | 'api_keys.revoke.own'
  | 'api_keys.revoke.all'
  | 'dashboard.read'
  | 'system.config';

export interface UserProfile {
  id: string;
  displayName: string;
  avatarUrl: string | null;
  email: string | null;
  emailVerified: boolean;
  emailVerifiedAt: string | null;
  authProvider: 'email' | 'google' | 'github';
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface AuthContextType {
  user: User | null;
  session: Session | null;
  profile: UserProfile | null;
  roles: AppRole[];
  permissions: AppPermission[];
  isLoading: boolean;
  // Convenience booleans
  isSuperAdmin: boolean;
  isAdmin: boolean;       // true for super_admin OR admin (backwards compat)
  isModerator: boolean;
  isEmailVerified: boolean;
  // Methods
  signOut: () => Promise<void>;
  hasRole: (role: AppRole) => boolean;
  hasPermission: (permission: AppPermission) => boolean;
  refreshProfile: () => Promise<void>;
}

export interface ApiKey {
  id: string;
  userId?: string;
  name: string;
  keyPrefix: string;
  scopes: AppPermission[];
  expiresAt: string | null;
  lastUsedAt: string | null;
  revokedAt: string | null;
  createdAt: string;
}

export interface ApiKeyCreateInput {
  name: string;
  scopes: AppPermission[];
  expiresAt?: string | null;
}

export interface ApiKeyCreateResponse {
  apiKey: ApiKey;
  rawKey: string;
}

export interface OAuthProvider {
  id: 'google' | 'github';
  name: string;
  connected: boolean;
  email?: string | null;
}

export interface UserIdentity {
  id: string;
  provider: 'google' | 'github' | 'email';
  providerEmail: string | null;
  linkedAt: string;
}

export interface AdminUserView {
  id: string;
  email: string;
  profile: UserProfile | null;
  roles: AppRole[];
  last_sign_in_at: string | null;
  created_at: string;
}

// Permission groups for UI display
export const PERMISSION_GROUPS: Record<string, AppPermission[]> = {
  'การสนทนา': [
    'conversations.read.own',
    'conversations.write.own',
    'conversations.delete.own',
  ],
  'หน่วยงาน': ['agencies.read'],
  'API Keys': ['api_keys.read.own', 'api_keys.write.own', 'api_keys.revoke.own'],
};

export const ROLE_LABELS: Record<AppRole, string> = {
  super_admin: 'Super Admin',
  admin: 'Admin',
  moderator: 'Moderator',
  user: 'User',
  api_user: 'API User',
};

export const ROLE_COLORS: Record<AppRole, string> = {
  super_admin: 'bg-red-100 text-red-800 border-red-200',
  admin: 'bg-orange-100 text-orange-800 border-orange-200',
  moderator: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  user: 'bg-blue-100 text-blue-800 border-blue-200',
  api_user: 'bg-gray-100 text-gray-800 border-gray-200',
};
