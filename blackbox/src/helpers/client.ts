import axios, { type AxiosInstance } from "axios";

export const API_URL = (): string => process.env.API_URL ?? "http://localhost:8080";

export function createApi(token?: string): AxiosInstance {
  return axios.create({
    baseURL: API_URL(),
    // Never throw on HTTP status; tests assert on resp.status directly.
    validateStatus: () => true,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}
