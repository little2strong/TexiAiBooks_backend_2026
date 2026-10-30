import type { Staff, StaffLoginResult } from "../api/types";

let current: { token: string; staff: Staff; expiresAt: number } | null = null;
const listeners = new Set<() => void>();
let expiryTimer: ReturnType<typeof setTimeout> | undefined;
let notice: string | null = null;

export const session = {
  get: () => current,
  token: () =>
    current && current.expiresAt > Date.now() ? current.token : null,
  start: (result: StaffLoginResult) => {
    notice = null;
    clearTimeout(expiryTimer);
    current = {
      token: result.access_token,
      staff: result.staff,
      expiresAt: Date.now() + result.expires_in * 1000,
    };
    expiryTimer = setTimeout(() => session.end('Your session has expired. Sign in again.'), result.expires_in * 1000);
    listeners.forEach((listener) => listener());
  },
  notice: () => notice,
  end: (reason?: string) => {
    notice = reason || null;
    clearTimeout(expiryTimer);
    current = null;
    listeners.forEach((listener) => listener());
  },
  subscribe: (listener: () => void) => {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};
