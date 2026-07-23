export const MIN_PASSWORD_LENGTH = 6;

export interface ChangePasswordInput {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

/** Returns an error message (Thai) or null when the input is valid. */
export function validateChangePassword({
  currentPassword,
  newPassword,
  confirmPassword,
}: ChangePasswordInput): string | null {
  if (!currentPassword) return 'กรุณากรอกรหัสผ่านปัจจุบัน';
  if (newPassword.length < MIN_PASSWORD_LENGTH) return 'รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร';
  if (newPassword !== confirmPassword) return 'รหัสผ่านใหม่ไม่ตรงกัน';
  return null;
}
