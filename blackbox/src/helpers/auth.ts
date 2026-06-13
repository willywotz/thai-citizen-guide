import type { AxiosInstance } from "axios";
import { createApi } from "./client";
import { ROLE_ACCOUNTS, type Role } from "../access-matrix";

export async function login(email: string, password: string): Promise<string> {
  const resp = await createApi().post("/api/v1/auth/login", { email, password });
  if (resp.status !== 200) {
    throw new Error(`login failed for ${email}: ${resp.status} ${JSON.stringify(resp.data)}`);
  }
  return resp.data.access_token as string;
}

export async function adminApi(): Promise<AxiosInstance> {
  const token = await login(
    process.env.ADMIN_EMAIL ?? "admin@example.com",
    process.env.ADMIN_PASSWORD ?? "admin1234",
  );
  return createApi(token);
}

const tokenCache = new Map<Role, string>();

export async function loginAs(role: Role): Promise<AxiosInstance> {
  let token = tokenCache.get(role);
  if (!token) {
    token = await login(ROLE_ACCOUNTS[role].email, process.env.TEST_USER_PASSWORD ?? "blackbox1234");
    tokenCache.set(role, token);
  }
  return createApi(token);
}
