import { Tag, Tooltip } from 'antd';
import { statusGlossary } from '../lib/business';
import { label } from '../lib/format';

const colors: Record<string, string> = {
  new: 'info', in_review: 'review', waiting_on_driver: 'warning', ready_to_file: 'ready', filed: 'filed',
  draft: 'warning', pending: 'warning', confirmed: 'income', reversed: 'neutral', clean: 'income', generated: 'income',
  claimable: 'income', excluded: 'expense', personal: 'neutral', failed: 'expense', active: 'income',
  rejected: 'expense', overdue: 'expense', in_preparation: 'review', awaiting_driver: 'warning', driver_approved: 'ready', approved: 'ready',
  retired: 'neutral', received: 'info', in_progress: 'review', completed: 'income', accepted: 'income', corrected: 'warning', valid: 'income',
  expiring_soon: 'warning', expired: 'expense', no_expiry: 'neutral', mandated: 'warning', upcoming: 'info', not_required: 'neutral', voluntary: 'info',
  exit_eligible: 'ready', exempt: 'neutral', ceased: 'neutral', inactive: 'neutral', below: 'income', approaching: 'warning', over: 'expense',
};
export function StatusBadge({ status }: { status: string }) {
  const explanation = statusGlossary[status];
  const description = explanation ? `${explanation.meaning} Next owner: ${explanation.owner}. Next: ${explanation.trigger}. Status changes are recorded by the backend; they are not automatic.` : 'Status returned by the server. Meaning and next owner are not configured; ask an administrator.';
  return <Tooltip title={description}><Tag tabIndex={0} aria-label={`${label(status)}. ${description}`} className="status-badge" data-tone={colors[status] || 'neutral'}><span className="status-dot" aria-hidden="true" />{label(status)}</Tag></Tooltip>;
}
