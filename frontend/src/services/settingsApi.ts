import { api } from "@/lib/apiClient";
import type { SettingsResponse, SettingUpdate } from "@/types/settings";

export const getSettings = (): Promise<SettingsResponse> =>
  api.get<SettingsResponse>("/api/v1/settings");

export const updateSettings = (settings: SettingUpdate[]): Promise<{ detail: string }> =>
  api.put<{ detail: string }>("/api/v1/settings", { settings });