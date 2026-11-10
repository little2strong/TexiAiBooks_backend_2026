import type { Role } from '../api/types';

export type Action = 'read' | 'edit' | 'assign' | 'approve_submission' | 'reveal' | 'note' | 'message' | 'export' | 'admin';
// Mirrors the backend: admins can do everything; accountants do the day-to-day
// work on their assigned drivers but cannot assign, file or administer.
const adminOnly: Action[] = ['admin', 'assign', 'approve_submission'];
export function can(role: Role | undefined, action: Action): boolean {
  if (!role) return false;
  if (role === 'admin') return true;
  return !adminOnly.includes(action);
}
