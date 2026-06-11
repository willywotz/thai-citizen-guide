import { describe, it, expect } from 'vitest';
import { validateCreateMode, MIN_PASSWORD_LENGTH } from './userForm';

describe('validateCreateMode', () => {
  it('accepts a valid password when not inviting', () => {
    expect(validateCreateMode({ sendInvite: false, password: 'secret123' })).toBeNull();
  });

  it('accepts invite with no password', () => {
    expect(validateCreateMode({ sendInvite: true, password: '' })).toBeNull();
  });

  it('rejects a too-short password', () => {
    expect(validateCreateMode({ sendInvite: false, password: '123' })).toMatch(/อย่างน้อย/);
  });

  it('rejects empty password when not inviting', () => {
    expect(validateCreateMode({ sendInvite: false, password: '' })).toMatch(/รหัสผ่าน/);
  });

  it('exposes the shared minimum length', () => {
    expect(MIN_PASSWORD_LENGTH).toBe(6);
  });
});
