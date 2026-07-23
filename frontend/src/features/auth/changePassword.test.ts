import { describe, it, expect } from 'vitest';
import { validateChangePassword } from './changePassword';

const ok = { currentPassword: 'oldsecret', newPassword: 'newsecret123', confirmPassword: 'newsecret123' };

describe('validateChangePassword', () => {
  it('accepts a valid change', () => {
    expect(validateChangePassword(ok)).toBeNull();
  });

  it('requires the current password', () => {
    expect(validateChangePassword({ ...ok, currentPassword: '' })).toMatch(/ปัจจุบัน/);
  });

  it('rejects a too-short new password', () => {
    expect(validateChangePassword({ ...ok, newPassword: '123', confirmPassword: '123' })).toMatch(/อย่างน้อย/);
  });

  it('rejects a mismatched confirmation', () => {
    expect(validateChangePassword({ ...ok, confirmPassword: 'different' })).toMatch(/ไม่ตรงกัน/);
  });
});
