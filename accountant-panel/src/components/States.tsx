import { Alert, Button, Skeleton } from 'antd';
import type { ReactNode } from 'react';

export function QueryState({ pending, error, retry, children }: { pending: boolean; error: Error | null; retry: () => unknown; children: ReactNode }) {
  if (pending) return <div className="surface state-padding" aria-label="Loading content"><Skeleton active paragraph={{ rows: 6 }} /></div>;
  if (error) return <Alert type="error" showIcon title="Unable to load this view" description={error.message}
    action={<Button onClick={() => retry()}>Retry</Button>} />;
  return children;
}
