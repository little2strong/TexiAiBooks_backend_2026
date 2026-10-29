import type { Role } from '../api/types';

export type Action = 'read' | 'edit' | 'assign' | 'approve_submission' | 'reveal' | 'note' | 'message' | 'export' | 'admin';
export function can(role: Role | undefined, action: Action): boolean {
  if (!role) return false;
  if (action === 'read' || action === 'note') return true;
  if (action === 'admin') return role === 'admin';
  if (action === 'assign' || action === 'approve_submission') return role === 'admin' || role === 'senior_accountant';
  if (action === 'edit' || action === 'reveal' || action === 'message' || action === 'export') return role !== 'support';
  return false;
}
