import type { ReactNode } from 'react';
import { can, type Action } from '../auth/permissions';
import { useSession } from '../auth/context';

export function RoleGuard({ action, children, fallback = null }: { action: Action; children: ReactNode; fallback?: ReactNode }) {
  const active = useSession();
  return can(active?.staff.role, action) ? children : fallback;
}
