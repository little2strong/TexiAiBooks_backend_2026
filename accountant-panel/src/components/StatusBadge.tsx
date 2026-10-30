import { Tag, Tooltip } from 'antd';
import { statusGlossary } from '../lib/business';
import { label } from '../lib/format';

const colors: Record<string, string> = {
  new: 'info', in_review: 'review', waiting_on_driver: 'warning', ready_to_file: 'ready', filed: 'filed',
  draft: 'warning', pending: 'warning', confirmed: 'income', reversed: 'neutral', clean: 'income', generated: 'income',
  claimable: 'income', excluded: 'expense', personal: 'neutral', failed: 'expense', trialing: 'info', active: 'income',
  rejected: 'expense', overdue: 'expense',
};
export function StatusBadge({ status }: { status: string }) {
  const explanation = statusGlossary[status];
  const description = explanation ? `${explanation.meaning} Next owner: ${explanation.owner}. Next: ${explanation.trigger}. Status changes are recorded by the backend; they are not automatic.` : 'Status returned by the server. Meaning and next owner are not configured; ask an administrator.';
  return <Tooltip title={description}><Tag tabIndex={0} aria-label={`${label(status)}. ${description}`} className="status-badge" data-tone={colors[status] || 'neutral'}><span className="status-dot" aria-hidden="true" />{label(status)}</Tag></Tooltip>;
}
