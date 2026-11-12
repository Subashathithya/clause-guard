import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BellOff, CalendarDays, CircleAlert } from 'lucide-react';
import { api } from '../api';
import { useAsync } from '../hooks';
import type { DateKind, Reminder } from '../types';
import { Card, EmptyState, PageHeader } from '../components/ui/data';
import { Button, Tag } from '../components/ui/primitives';
import { useI18n } from '../i18n/I18nProvider';

const KIND_KEYS: Record<DateKind, string> = {
  payment: 'tracking.kindPayment',
  renewal: 'tracking.kindRenewal',
  notice: 'tracking.kindNotice',
  termination: 'tracking.kindTermination',
  other: 'tracking.kindOther',
};

function relative(days: number): string {
  if (days < 0) return `Overdue by ${Math.abs(days)} ${Math.abs(days) === 1 ? 'day' : 'days'}`;
  if (days === 0) return 'Due today';
  return `In ${days} ${days === 1 ? 'day' : 'days'}`;
}


function ReminderRow({ reminder }: { reminder: Reminder }) {
  const { t, formatDate } = useI18n();
  return (
    <li className={['reminder-row', reminder.is_overdue ? 'reminder-row-overdue' : ''].join(' ')}>
      <div className="reminder-ico" aria-hidden="true">
        {reminder.is_overdue ? <CircleAlert size={18} /> : <CalendarDays size={18} />}
      </div>
      <div className="reminder-body">
        <div className="row-inline" style={{ gap: 8, flexWrap: 'wrap' }}>
          <strong>{reminder.label}</strong>
          <Tag>{t(KIND_KEYS[reminder.kind])}</Tag>
          <span className={reminder.is_overdue ? 'date-overdue' : 'text-sm muted'}>
            {relative(reminder.days_until)}
          </span>
        </div>
        <p className="text-sm muted mb-0 mt-2">
          {reminder.contract_name} · {formatDate(`${reminder.due_date}T00:00:00`)}
        </p>
        {reminder.notes && <p className="text-sm mb-0 mt-2">{reminder.notes}</p>}
        <p className="text-xs faint mb-0 mt-2">
          {t('notifications.reminderSetFor', { date: formatDate(`${reminder.remind_on}T00:00:00`) })}
          {reminder.remind_days_before > 0
            ? ` · ${reminder.remind_days_before} ${reminder.remind_days_before === 1 ? 'day' : 'days'} before`
            : ''}
        </p>
      </div>
      <Link
        to={`/contracts/${reminder.contract_id}`}
        className="btn btn-secondary btn-sm reminder-link"
      >
        {t('common.open')} <ArrowRight size={14} />
      </Link>
    </li>
  );
}

export default function Notifications() {
  const { t } = useI18n();
  const [days, setDays] = useState(30);
  const { value, loading, error, retry } = useAsync<Reminder[]>(() => api.reminders(days), [days]);
  const reminders = value || [];
  const overdue = reminders.filter((r) => r.is_overdue);
  const upcoming = reminders.filter((r) => !r.is_overdue);

  return (
    <div>
      <PageHeader
        title={t('notifications.title')}
        lead={t('notifications.lead')}
      />

      <div className="card card-pad row-spread mb-4">
        <p className="text-sm muted mb-0" style={{ maxWidth: 560 }}>
          {t('notifications.inAppOnly')}
        </p>
        <div className="row-inline" style={{ gap: 8 }} aria-label={t('notifications.windowLabel')}>
          {[7, 30, 90].map((d) => (
            <Button
              key={d}
              size="sm"
              variant={days === d ? 'primary' : 'secondary'}
              onClick={() => setDays(d)}
              aria-pressed={days === d}
            >
              {t(`notifications.next${d}`)}
            </Button>
          ))}
        </div>
      </div>

      {loading && !value ? (
        <Card><p className="text-sm muted mb-0">{t('notifications.loading')}</p></Card>
      ) : error && !value ? (
        <Card>
          <p className="text-sm muted">{error}</p>
          <Button size="sm" variant="secondary" onClick={retry}>{t('common.tryAgain')}</Button>
        </Card>
      ) : reminders.length === 0 ? (
        <Card>
          <EmptyState
            icon={<BellOff size={26} />}
            title={t('notifications.nothingComingUp')}
            description={
              <>{t('notifications.nothingComingUpBody')}</>
            }
            action={<Link to="/contracts" className="btn btn-secondary">{t('notifications.goToContracts')}</Link>}
          />
        </Card>
      ) : (
        <div className="stack">
          {overdue.length > 0 && (
            <Card title={t('notifications.overdueGroup', { count: overdue.length })}>
              <ul className="reminder-list">
                {overdue.map((r) => <ReminderRow key={r.id} reminder={r} />)}
              </ul>
            </Card>
          )}
          <Card title={t('notifications.comingUpGroup', { count: upcoming.length })}>
            {upcoming.length === 0 ? (
              <p className="text-sm muted mb-0">{t('notifications.noDatesInWindow')}</p>
            ) : (
              <ul className="reminder-list">
                {upcoming.map((r) => <ReminderRow key={r.id} reminder={r} />)}
              </ul>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
