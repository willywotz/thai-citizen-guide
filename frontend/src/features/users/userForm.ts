export const MIN_PASSWORD_LENGTH = 6;

export interface CreateModeInput {
  sendInvite: boolean;
  password: string;
}

/** Returns an error message (Thai) or null when the create-mode input is valid. */
export function validateCreateMode({ sendInvite, password }: CreateModeInput): string | null {
  if (sendInvite) return null;
  if (!password) return 'กรุณากรอกรหัสผ่าน';
  if (password.length < MIN_PASSWORD_LENGTH) return 'รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร';
  return null;
}
