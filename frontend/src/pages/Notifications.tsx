import { BellOff } from 'lucide-react';
import { Card, EmptyState, PageHeader } from '../components/ui/data';

export default function Notifications() {
  return (
    <div>
      <PageHeader
        title="Notifications"
        lead="Updates about your documents and your account."
      />
      <Card>
        <EmptyState
          icon={<BellOff size={26} />}
          title="You're all caught up"
          description={
            <>
              There are no notifications right now. When there’s something worth knowing — like a quota
              update or a new feature — it will appear here.
            </>
          }
        />
      </Card>
    </div>
  );
}