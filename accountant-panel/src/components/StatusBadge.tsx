import { Tag } from 'antd';
import { label } from '../lib/format';

const colors: Record<string, string> = {
  new: 'info', in_review: 'review', waiting_on_driver: 'warning', ready_to_file: 'ready', filed: 'filed',
  draft: 'warning', pending: 'warning', confirmed: 'income', reversed: 'neutral', clean: 'income', generated: 'income',
  claimable: 'income', excluded: 'expense', personal: 'neutral', failed: 'expense', trialing: 'info', active: 'income',
  rejected: 'expense', overdue: 'expense',
};
export function StatusBadge({ status }: { status: string }) {
  return <Tag className="status-badge" data-tone={colors[status] || 'neutral'}><span className="status-dot" aria-hidden="true" />{label(status)}</Tag>;
}
